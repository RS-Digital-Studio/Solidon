# ROADMAP — Arbeitsliste

Abzuarbeiten von oben nach unten. Jeder Punkt ist so geschnitten, dass danach
die Suite grün sein kann. Details stehen im Bauplan (§-Verweise), Regeln in
`AGENTS.md`.

Legende: `[ ]` offen · `[~]` in Arbeit · `[x]` fertig und Suite grün

---

## Was offen ist

Die offenen Punkte stehen weit auseinander: ein paar in den Phasen, die meisten
in den Durchsichten der letzten Tage. (Keine Zahl in diesem Absatz: Sie stünde
neben einer Tabelle, die sie schon nennt, und wäre die Erste, die driftet.)

Diese Übersicht ist die Abkürzung, nicht die Quelle. Der Punkt selbst steht mit
seiner Begründung an seinem Ort, und dort wird er auch geändert; hier steht nur,
dass es ihn gibt und worauf er wartet. **Ein Register, dem man nicht glaubt, ist
schlechter als keines** — deshalb hält `tests/test_roadmap.py` beides zusammen:
Wer einen Punkt abhakt oder einen neuen aufmacht, ohne hier nachzuziehen,
bekommt einen roten Lauf.

**Was hier nicht mehr steht:** Bis zum 22.08.2026 war diese Datei die
Arbeitsliste und die Geschichte des Projekts in einem, und das Zweite überwog
weit — von 112 Abschnitten enthielten 78 keinen einzigen offenen Punkt. Sie
stehen jetzt in `ROADMAP-ARCHIV.md`, mit einem datierten Verzeichnis. Nichts ist
verloren, und gesucht wird dort wie hier über den Text; was sich geändert hat,
ist, dass diese Datei lesbar geworden ist. Wer wissen will, was an einer Stelle
schon versucht wurde, sucht im Archiv — das ist das Teuerste, was das Projekt
hat.

**Und eine Warnung, die aus derselben Durchsicht kommt:** Ein offener Punkt
zählt nur, wenn er ein Kästchen hat. Vier Punkte lagen als Prosa in Abschnitten
ohne Kästchen — einer davon 163 Zeilen tief unter „Leistung (§31)", und er
besagt, dass ein roter Leistungstest nicht „nicht fertig" heißt. Kein Register
sah sie, kein Test zählte sie. Wer einen Fund festhält, gibt ihm ein Kästchen
oder er hält ihn nicht fest.

**Die Reihenfolge ist seit dem 22.08.2026 die Kundenwirkung, nicht die
Registerreihenfolge.** Robert hat den Auftrag so gefasst: „alles abarbeiten,
dass die App ein Meisterwerk wird und Kunden sehr zufrieden sind mit einfacher
Bedienung." Daraus folgt eine Rangfolge, die in dieser Tabelle nicht steht und
trotzdem gilt:

1. **Was ein Kunde als Fehler erlebt** — Abstürze zuerst. Ein Absturz ist das
   genaue Gegenteil von „sehr zufrieden", und fünf offene Punkte warten auf
   denselben Nachweis.
2. **Was ihn im Weg steht** — Fehlermeldungen ohne anklickbare Handlung,
   Bedienwege mit einem Klick zu viel, ein Startbildschirm, der rollt.
3. **Was seine Arbeit besser macht** — Erkennung, Karten mit Zahlen statt
   Farben, Vorschläge, die stimmen.
4. **Was ihn schützt, ohne dass er es sieht** — Testarten, Tor, Werkzeuge.
   Zuletzt, aber nicht weglassbar: Vier von fünf Nichtanschluss-Fällen eines
   einzigen Tages waren Versprechen, die das Produkt gab und nicht hielt.

Punkte, die eine **Entscheidung** brauchen, tragen sie in der dritten Spalte,
sobald sie gefallen ist — mit dem Namen dessen, der sie getroffen hat. Was die
Bedienung betrifft, entscheidet die Sitzung unter Roberts Vollmacht („mach
alles, damit es immer perfekt für Kunden ist"); was Produktrichtung, Geld oder
Verfahren betrifft, geht an ihn.

**Und was den Bauplan oder `AGENTS.md` ändert, geht immer an ihn — auch unter
Vollmacht.** Am 22.08.2026 hat 3d-druck-64 eine Bauplanänderung (§35, die
Testart „Anschluss") unter dieser Vollmacht entschieden und auf Widerspruch von
3d-druck-33 zurückgenommen. Deren Begründung war ein Satz, den dieselbe Sitzung
zwei Stunden zuvor selbst geschrieben hatte: *Wenn zwei Sitzungen sich
gegenseitig zurufen, was in die Regeln gehört, ändern wir die Regeln, nach denen
wir gerade beurteilt werden.* Eine Vollmacht für das Produkt ist keine für die
Hausordnung, und eine Vollmacht, die man **weitergereicht** bekommt, ist genau
der Weg, den beide Sitzungen kurz zuvor für falsch gehalten hatten.

| Punkt | steht unter | wartet auf |
|---|---|---|
| CI-Bauläufe, Signierung und Notarisierung | P8 — Erste Veröffentlichung | Feldläufe der Pakete, ein für Robert zugänglicher Windows-Signierdienst sowie Apple-Konto und Developer-IDs. Die gesperrten CI-Wege und alle Pakete stehen |
| Doku, Website, Lizenzhinweise | P8 — Erste Veröffentlichung | DMARC und den AVV im CCP. Das Postfach `support@solidon3d.de` existiert; SPF, MX und die Annahme von außen sind geprüft |
| Sichtbarkeit | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | keine Entwicklungsaufgabe — bleibt bewusst stehen |
| macOS ausliefern | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | Apple-Zertifikat und Notarisierung; der Paketierschritt steht |
| DMARC fehlt | Die Demo bis 30.10.2026 (12.08.2026) | einen TXT-Eintrag im CCP |
| VTK stirbt in der CI, und die Fenstertests laufen dort nicht mehr | Die Demo bis 30.10.2026 (12.08.2026) | Runner mit GL oder ein VTK, das ohne auskommt; bis dahin prüft die Fenster, wer einen Bildschirm hat |
| Ein Gewinde auf macOS kann als STL Löcher haben — **ein Weg ist gebaut, die Bestätigung fehlt** | Die Demo bis 30.10.2026 (12.08.2026) | einen Lauf auf einem Mac. Seit `d96308bb` wird ein offenes Netz aus geschlossener Form vernäht statt feiner vernetzt (T-Kreuzung, nicht Loch); ob der dortige Riss einer ist, lässt sich hier nicht erzeugen |
| Auf einem fremden Rechner installieren | Die Demo bis 30.10.2026 (12.08.2026) | einen fremden Rechner — die Dateien liegen seit dem 20.08. |
| Den helikalen Gang überall schließen | Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen | eine andere **Bauart** — alle sieben Griffe an `MakePipeShell` sind gemessen und widerlegt (20.08.), und ein Rotationskörper schraubt nicht |
| Der eine übersprungene Test | Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen | VTKs Zustand über mehrere Fenster hinweg |
| P16.10 — die Regel in der Sammlung | P16 — Organische Modellierung | eine Entscheidung; sie kostet zwei Agenten-Suite-Läufe und Geld |
| Der Absturz in einer einzelnen Datei | Ein Umgebungsartefakt, das keines war (14.08.2026) | einen ruhigen Baum und mehr als dreißig Läufe — dreißig am 20.08. blieben sauber, aber `panels.py` ist seit dem Fund fünfmal geändert worden |
| Die Suite gegen Sonnet 5 | Die Konzepte nachrecherchiert (19.08.2026) | zwei Läufe über den Schlüssel des Nutzers; bis dahin ist die Quote eine Annahme |
| Stegdicke und Kammertiefe sind nicht gemessen | Die Nutfeder, und zwei Fehler auf dem Weg dorthin (20.08.2026) | zwei Werte vom Messschieber an einer 2020er und einer 3030er Schiene; bis dahin stehen die gebräuchlichsten Katalogwerte da, und `note` nennt die Spanne |
| Verrundung und Fase gehen auf einem Netz nicht — **Konzept liegt vor** | Neun heruntergeladene Modelle durch die ganze Kette (21.08.2026) | **eine Entscheidung von Robert über eine Phase**, nicht über einen Commit: `konzepte/konzept-flaechenrueckgewinnung-2026-08.md`. Flächenrückgewinnung aus dem Netz, fünf Schritte, drei offene Fragen im dritten. Dagegen: **neun von neun** heruntergeladenen Modellen laufen dagegen |
| Der Verweisfilter schlüsselt nach Objekt-Kennungen, die im Stapel wechseln | Das Fundament der Wahrnehmung (22.08.2026) | eine Objektidentität über den Stapel hinweg — ein breiterer Schlüssel stellte die Fragenflut wieder her, die §15.7 begraben hat. Die Skizzenebenen-Hälfte desselben Fundes ist seit dem 26.08.2026 gebaut („irgendwo"-Menge) |
| Die Antwort der Zuordnung steht nirgends — **gebaut, Abnahme offen** | Das Fundament der Wahrnehmung (22.08.2026) | **einen Fall, der die Frage überhaupt noch stellt.** Feld, Serialisierung und Wiederverwendung stehen seit `67b0386`, zwei Einheitstests decken sie. Die Abnahmezahl (99 → 7 → 0) ist am 23.08. nicht nachzumessen gewesen: Weder eingelesene Zwillingsbohrungen noch erzeugte stellen heute eine Frage. Ursprünglich stand hier: die zweite Hälfte von Bauplan §15.7 — was eine **Operation** erfragt, steht seit `311134a` im Stapel; was die **Zuordnung** entscheidet (§21.3, die 99 Fenster), passt in keinen Parameter und braucht ein Feld an der Operation samt Formatänderung. Entwurf und offene Frage liegen in `.claude/memory/merkmalsmehrdeutigkeit-entwurf.md` |
| Ein Test, der nur seine eigene Konsistenz misst, sieht keinen systematischen Versatz | Das Fundament der Wahrnehmung (22.08.2026) | eine Frage an jede vorhandene Prüfung: gegen einen Wert von außen oder nur gegen die eigene Wiederholbarkeit? Zwei Fälle an einem Tag — die Krümmungskarte war bei jeder Netzfeinheit **gleich** falsch (zwei Drittel des wahren Radius), `ring_diameter` machte zwei verschieden große Tori ununterscheidbar |
| Parallelität und Schloss bedingen einander | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung über den Umbau des Tors — und die Reihenfolge darin. Gemessen: `-n 8` bringt Faktor 2,6, aber zwei Läufe nebeneinander machen den **fremden** rot (11 failed gegen 0). Der Deadlock kostet 10–27 min je Lauf und ist damit der größere Posten |
| Ein gescheiterter Merge ist ein Eingriff, kein Nichts | Das Fundament der Wahrnehmung (22.08.2026) | eine Regel im Verfahren: Wer einen Merge abbricht, prüft danach `git status` **und** `git stash list`. Der Autostash überlebt den Abbruch nicht zuverlässig und trifft im geteilten Baum fremde Arbeit |
| Der Haupt-Index altert, und `git status` lügt für alle mit | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung, ob das Verfahren mit privatem Index den Nachzug selbst übernimmt. Aufgeräumt wird mit `git reset` nach einer Sicherung von `.git/index`; am 23.08. stand er bei 1424 Löschungen gegenüber HEAD, am selben Abend nach sechs weiteren Commits bei **1824** — er altert also messbar mit jedem privaten Commit weiter, und zwar in die gefährliche Richtung. Zweimal aufgeräumt, beide Male ohne Verlust: keine Datei geändert, nur der Index |
| Das Prüfschloss serialisiert die Rechenzeit, nicht den Arbeitsbaum | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung über eigene Arbeitsbäume. Jeder Lauf liest die ungestageten Dateien aller Sitzungen — ein fremder Zwischenstand macht einen Lauf rot, und schlimmer: er kann ihn grün machen |
| Die Belegung heißt in `es` und `pt` noch nicht entschieden | Vier Wege von Hand, während die Suite grün war (23.08.2026) | eine Wortwahl, keine Messung: Elegoo sagt für `es` `bandeja` 65 gegen `placa` 18, für `pt` steht es 69:69. Bei unentschiedener Quelle bleibt der Bestand |
| Fünf Fensterdateien reißen **vor** ihrer Zusammenfassung | Vier Wege von Hand, während die Suite grün war (23.08.2026) | zehn Läufe je Seite (~40 min Rechenzeit). Die Sammelgruppen-Hypothese ist gemessen und **zurückgezogen** — 1 gegen 2 von je 4 liegt im Rauschen. Einzeln laufen alle Dateien sauber; die Aufräum-Fixture ist per A/B entlastet (4/4 gegen 3/4). Rate 25 bis 50 Prozent je Datei, Code 0xC0000374. **Fortschreibung 25.08.2026 (c1fcb9ea):** Todesweg ist die **Referenzzählung**, nicht der Sammler — beide gc-Anläufe (aus + gezieltes Sammeln, aus + gar nichts) sind gemessen und verworfen, Notiz in `tests/conftest.py`. Mit dem Testbestand vom 25.08. riss `test_ui.py` deterministisch (3/3, Position wandert mit der Zusammensetzung); seit dem Suite-Pin (`_windows_live_to_the_end`) stellt die Suite den tragenden Zustand **absichtlich** her — Fenster leben bis zum Prozessende, der Riss liegt wieder hinter der Zusammenfassung. Die Mine selbst — C++-Zerstörung eines VTK-Fensters mitten im Prozess — bleibt offen; wer sie angeht, misst gegen den Bestand vom 25.08. **Fortschreibung 26.08.2026:** `test_analysis_ui.py` riss zweimal von zweimal **vor** der Zusammenfassung (einmal im Tor, einmal solo — aber unter Vier-Sitzungen-Last), Access Violation beim 24. Test, Stack im `super().__init__()` des Preview-Workers (`session.py:223` ← `preview_async`). Die Zeile ist als Ursache **ausgeschlossen**: ces Tages-Commits berühren sie nicht, und ce maß 3/3 grün solo auf ruhiger Maschine. Die Kombination ist die Auskunft — lastabhängig, die Familie in neuer Position, und der Stack nennt den Moment, nicht den Grund. Dieselbe Datei zeigte am selben Tag eine **dritte Gestalt** (a2, Torlauf): neunzehn Minuten Stillstand bei 0,015 CPU-Sekunden und 0 Bytes Ausgabe, dann von selbst gelöst und grün — als Beobachtung belegt, als Diagnose nicht; die Signatur passt zum Abbau-Deadlock (Signatur C, eine Zeile tiefer). **Fortschreibung 26.08.2026, `test_print_settings_ui.py` (d1 und ce):** Die schärfste Messung bisher, weil beide Richtungen belegt sind. Nach dem Plattenwahl-Commit (`78f559d0`) riss die Datei mit `-p no:randomly` reproduzierbar an Position 57; im Arbeitsbaum auf dem Stand davor lief sie mit 73 passed durch. **Und trotzdem lag es nicht am Inhalt der neuen Tests:** Ein trivialer 75. Test an derselben Stelle war folgenlos, der Absturz traf nie einen der neuen, sondern den Abbau von `test_switching_the_slicer_empties_the_profile_choice`, und das Zusammenlegen beider Tests zu einem verschob ihn nur von 57 auf 58. Damit ist gemessen, was die conftest-Notiz behauptet: Es zählt die Zusammensetzung, nicht ein Test — aber auch nicht die bloße Anzahl. Behoben durch Umzug in die Sammelgruppe (`77c0f5d5`), nicht durch eine Reparatur; wer die Mine entschärft, kann den Test zurückholen. Lehre nebenbei: Die erste Zuschreibung lautete „bekannte Familie, kein Verdacht gegen den Commit" — die Gegenprobe auf dem Stand davor kostete zwei Minuten und widerlegte sie. **Fortschreibung 30.08.2026 (72 und d5, unabhängig):** `test_print_settings_ui.py` reißt jetzt mit **139 im Teardown der Aufräum-Fixture** (`conftest.py:836`, `_no_worker_outlives_its_window`) nach 63–64 grünen Punkten — in der Release-Kontrolle und im Waisen-Tor am selben Tag, einzeln reproduzierbar, und auf purem HEAD ohne die Tagesänderung identisch (Gegenprobe 72): dritte Code-Gestalt der Familie, erstmals mit benannter Stelle. Nach D13 (`5b7e4a46`, 15/53) erneut bestätigt: auf HEAD pur identisch, und die Rissstelle wandert mit der Testzahl — die Zusammensetzung zählt, wie schon bei `test_ui` gemessen. Neuer Fundort 30.08.2026 (72, im Tor vor `d91798b3`): `test_widget_lifetime.py` mit Exit 127 (`0xc0000374`, Heap) — Gegenprobe auf HEAD pur 1 von 2 gerissen, Familie, der Tagesdiff ist entlastet |
| Signatur C: der Hänger — kein Absturz, sondern Stillstand | Vier Wege von Hand, während die Suite grün war (23.08.2026) | eine **Messstelle**, die eine Änderung in wenigen Läufen bewertet statt in zwanzig. Drei Behebungsversuche sind gemessen und widerlegt. Hauptthread hält den GIL und wartet auf einen Qt-Mutex, Nebenthread umgekehrt — **B stirbt sofort, C stirbt gar nicht** |
| Zwei Pakete lösen den Deadlock noch nicht auf | Ein Deadlock, der keiner war — und sieben Pakete statt einem (23.08.2026) | einen **Verhaltenswechsel**, keinen Strukturfix — und deshalb je einen eigenen Schritt. `activation`: 223 Zeilen Code an der Lizenzgrenze im `__init__`, die Ladereihenfolge dort ändert man nicht, ohne die Grenze mitzuprüfen. `knowledge.parts`: dort **ist** der Import die Registrierung — die fünf Modulimporte füllen das Bausteinregister, und `bootstrap.load_operations` verlässt sich darauf; verzögert wären sie wirkungslos. Die anderen fünf Pakete sind seit dem 23.08. sauber, `tests/test_core_isolation.py` führt beide Namen mit Begründung |
| `3D Drucker/` liegt nur auf einer Maschine | Vier Wege von Hand, während die Suite grün war (23.08.2026) | eine Entscheidung von Robert: eigenes `.git`, **kein Remote**, 458 MB, 83 nicht committete Dateien. Kein Entwicklungsthema, sondern ein Datenthema — fällt die Platte aus, ist die Arbeit an den Druckprojekten weg |
| Vier Stapel zeigen auf `session.py:1515` | Was ein Kunde beim Öffnen der Beispiele sieht (23.08.2026) | eine **Lebensdaueruntersuchung**, keinen `gc`-Schutz: Der Sammler ist an zwei Messungen zu verschiedenen Zeiten als Ursache ausgeschlossen. Und die vier Stapel sind ein Zeuge, viermal gefragt — `wait(50)` blockiert in C, der Rahmen steht dort ohnehin. Der Weg führt über die Aufräum-Fixture und trifft damit **jede** Fensterdatei |
| `test_ui.py` stirbt bei zufälliger Testreihenfolge | Zwei Torläufe an einem Tag, beide an derselben Stelle (26.08.2026) | eine **Zuordnung zur Absturzfamilie**. Gemessen: mit `-p no:randomly` laufen alle 303 Tests durch (Exit 0), mit zufälliger Reihenfolge Zugriffsverletzung bei 23 % — beide Male in `panels.py` unter `_show_scene`, einmal `show_result`, einmal `show_document`. **Keine Regression**: Der Grundlagen-Torlauf vor allen Änderungen des Tages zeigte denselben Abbruch an derselben Stelle. Gehört zu den Signaturen A–C weiter oben; was fehlt, ist die Entscheidung, ob die Suite die Reihenfolge für diese Datei festnagelt oder die Ursache weiter verfolgt wird. **Dritte Beobachtung am 26.08.2026 (ce, Torlauf):** wieder bei 23 %, diesmal aber im `QCompleter`-Konstruktor (`op_dialog.py:197`, aus der fx-Hilfe `2b48f288`) statt in `panels.py` — die Position im Lauf ist stabil, die Stelle im Code nicht. Der betroffene Test allein: grün. Vollständige Wiederholung derselben Datei: 305 passed, Exit 0. Das ist die Auskunft, die zur Reihenfolge passt und gegen eine Regression spricht — der Torlauf davor am selben Tag kannte den Abbruch nicht, und die Änderungen dazwischen (Plattenwahl im Druckdialog) berühren weder `op_dialog` noch `panels`. **Vierte Messung am 27.08.2026 (30):** Die Datei trägt inzwischen **307** statt 303 Tests, und der Satz „mit `-p no:randomly` laufen alle durch" gilt nicht mehr — drei Läufe unter dem Schloss, mit fester Reihenfolge, gaben **1 von 3**: einmal Zugriffsverletzung bei 70 Prozent, zweimal 307 passed. Stelle wie gehabt `panels.py` unter `_show_scene`, diesmal `show_result`, ausgelöst aus `_with_two_objects` über `wait_for_idle`. Damit ist die Reihenfolge als Bedingung **widerlegt** und die Zusammensetzung bestätigt: Vier Tests mehr genügen, um die Mine auch bei fester Reihenfolge scharf zu machen. Eine Zuschreibung an die Commits des Tages ist bei dieser Rate nicht führbar — sie bräuchte viele Läufe je Seite —, und der Absturzstapel führt durch `main_window.py`, das während der Messung von einer anderen Sitzung geändert wurde. `test_operation_ui.py` riss im selben Torlauf mit und lief einzeln mit 67 passed durch: dort war es Fremdlast |
| Entwurfsvermerk auf den Rechtstexten | Was erst am Verkaufsstart fällig wird (24.08.2026) | die fachliche Prüfung. Eine Zeile in `tools/make_legal.py:236` und ein Neuerzeugen — die drei HTML-Dateien von Hand zu ändern hielte bis zum nächsten Lauf |
| Impressum ohne USt-IdNr. oder Steuernummer | Was erst am Verkaufsstart fällig wird (24.08.2026) | die Gewerbeanmeldung. §5 TMG verlangt sie, sobald es sie gibt; bis dahin nicht nachholbar |
| Offscreen prüft nichts, was am Aktor hängt | Ein Knopf, der einen Schritt legte und nichts bewegte (24.08.2026) | nur noch die Entscheidung, **welche Zusagen** an der Messstelle geprüft werden — die Messstelle selbst existiert seit `e2102440` (`tools/window_bench.py`, echtes Fenster, Posten-Zerlegung). `Viewport.show_scene` kehrt bei `self.plotter is None` vor dem Aktor-Aufbau zurück (`app/ui/viewport.py:1948`), und `tests/conftest.py` setzt `QT_QPA_PLATFORM=offscreen` für die ganze Suite — jede Zusage über Aktoren, Farben, Kamerastellung oder Bildinhalt ist dort grün über einer leeren Menge. Belegt am 24.08.: `_actors` war vor **und** nach einer Operation `{}`; mit sichtbarem Fenster wanderten dieselben Aktoren von (-10..10) auf (-104..-84, 84..104, 0..20) |
| Ein Prüfstand, der beim Fehlschlag modal stehen bleibt | Ein Knopf, der einen Schritt legte und nichts bewegte (24.08.2026) | eine Entscheidung, ob ein Prüfstand `report_error` abschalten darf. Ein Fehler öffnet dort einen modalen Dialog: Der Hauptthread stand, die Timer feuerten nicht mehr, und von außen war es von einem Hänger nicht zu unterscheiden — der Traceback lag still unter `%LOCALAPPDATA%\RS Digital\Solidon3D\reports\bericht-<zeitstempel>\bericht.txt` |
| 43 Texte stehen wortgleich in mehreren Dateien | Fünf Doppelungen, und eine hatte schon Folgen (24.08.2026) | niemanden — der Rest ist klein und lohnt keinen eigenen Durchgang. Die vier Fälle in `app/ui/main_window.py` sind am 24.08.2026 erledigt (`791a1576`); übrig sind Vorkommen, die meist zwei- bis dreimal in derselben Datei stehen |
| Wirkt die Typprüfung an `overlay.py:294` gegen den Torlauf-Riss? | Was niemand las, und was zweimal dastand (24.08.2026) | den nächsten Torlauf unter Last als Wirkungsnachweis — die Serie selbst ist erledigt (`bce88ff8`): Der Griff steht einmal (`leash.stop_watching_the_dying`), gemessen schlägt er nur in `OverlayHost` an (119 von vier Millionen Filteraufrufen, die sechs anderen Stellen null Mal — sie bleiben als Vorsorge), und der zweite Fund fällt aus anderem Grund: ein fremder Wrapper unter recyceltem Zeiger, gegen den `isValid` nichts sagt |
| Die Versicherung trägt die Rechtsformentscheidung und steht in keiner Liste | Die Haftungsgrundlagen des Geschäftsmodells nachkontrolliert (24.08.2026) | ein Angebot. Für Personen- und Sachschäden aus einem fehlerhaften Produkt braucht es eine **Produkthaftpflicht mit Software-Einschluss**, nicht nur die übliche Vermögensschadendeckung: Richtlinie (EU) 2024/2853 macht Software ausdrücklich zum Produkt, Umsetzungsfrist 09.12.2026, und der Verkaufsstart liegt danach |
| Der Haftungsausschluss der EULA wirkt nur mit einem Häkchen im Bestellvorgang | Die Haftungsgrundlagen des Geschäftsmodells nachkontrolliert (24.08.2026) | eine Bestellstrecke, die es noch nicht gibt. `EULA.md` Nummer 10 — kein Prüfinstitut, keine zugesicherte Maßhaltigkeit, keine tragenden Teile — ist gegenüber Verbrauchern eine negative Beschaffenheitsvereinbarung und nach § 327h BGB **ausdrücklich und gesondert** zu vereinbaren. Betrifft nur den späteren Verkauf; die PayPal-Spende hat keine Gegenleistung |
| Was der Zahlungsdienstleister vorn abnimmt, holt er hinten zurück | Die Haftungsgrundlagen des Geschäftsmodells nachkontrolliert (24.08.2026) | den Vertrag des Merchant of Record vor der Unterschrift. Er wickelt nur den späteren Lizenzkauf ab, nicht die PayPal-Spende. Seine Freistellung kann unbegrenzt und nach fremdem Recht gelten; `EULA.md` Nummer 11 wirkt gegenüber dem Kunden, nicht gegenüber dem Dienstleister. Bei einem Einzelunternehmen haftet dafür das Privatvermögen |
| Die orient_200-Marke fällt auf jeder Maschine einmal | Was der Gesamtreview liegen ließ (25.08.2026) | nichts — je Maschine die Marke neu setzen; die Säulenrechnung ist bewusst teurer und richtig (5c90fac6) |
| Das Schemabild des Skizzeneditors hinkt hinterher | Was der Gesamtreview liegen ließ (25.08.2026) | den Abschluss von 43s D-Paket — vorher ist die Zeichnung ein bewegliches Ziel |
| Rezepte rechnen ihren Hash bei jedem Start neu | Was der Gesamtreview liegen ließ (25.08.2026) | eine Gelegenheit — allein ist der Posten unmessbar klein. Die Startmarke ist seit dem 26.08.2026 entschieden und neu gesetzt; ihre Messung (`-X importtime`) zeigt: die Startzeit dominiert der Importblock trimesh/scipy/networkx, die Rezepte tauchen darin nicht auf |
| Verkaufsbereitschaft zum 15.10.2026 | Was Robert am 26.08.2026 aufgetragen hat | Finanzamt und Merchant of Record sowie spätestens am 25.10. der Verkaufsbau mit `DEMO_UNTIL = None` und `TRIAL_FROM = None`. Eine Verlängerung wäre nach der Entscheidung vom 28.08. kein automatischer Rückfall, sondern bräuchte eine neue ausdrückliche Entscheidung |
| Kommt xxhash im gebauten Paket an? | Eine Kunden-3MF hängt vier Minuten im Hash (30.08.2026) | den nächsten CI-Bau — die Diagnose ist durch (kein Hänger am frischen Prozess; jeder Kunde hashte 50-mal zu langsam, behoben mit `dedd2b8d`), aber die Kundenwirkung belegt erst das Paket selbst |
| Die Chat-Grundlast frisst drei Viertel des Fensters vor dem ersten Objekt | Der Chat-Kontext ist nach einem Objekt zu drei Vierteln voll (30.08.2026) | ein Paket „kompakte Werkzeugschemata" — die Messreihe ist durch (74 % Grundlast, ~600 Token je Zug, ~14–15 Züge Tragweite), die Stellschraube ist benannt |
| Ob die Eingabemethode im Flatpak jetzt erreichbar ist | Der erste Kundenbericht aus dem Feld (27.08.2026) | eine Rückmeldung desselben Kunden oder ein Linux-Gerät. Die zwei `--talk-name`-Zeilen für Fcitx sind ergänzt (`b21f8766`) und sind die üblichen aus Flathub-Manifesten; IBus liegt im Runtime. **Gebaut, Bestätigung offen** — von Windows aus nicht messbar |
| Ob der Start auf Wayland jetzt ohne Umwege geht | Der erste Kundenbericht aus dem Feld (27.08.2026) | **Korrektur gebaut, Feldbestätigung offen.** Martin Doneckers Ausgabe nennt `bad X server connection. DISPLAY=`; `fallback-x11` gab VTK unter Wayland keinen X11-Display. Das Flatpak erlaubt deshalb nur noch `--socket=x11`, sodass Qt und VTK gemeinsam über Xwayland laufen. Der einmalige Gegenversuch ist `flatpak run --socket=x11 --nosocket=wayland --nosocket=fallback-x11 de.rsdigital.solidon3d` |
| Ob die Übergabe an den Slicer im Flatpak jetzt ankommt | Der erste Kundenbericht aus dem Feld (27.08.2026) | eine Rückmeldung oder ein Linux-Gerät. Vier Startpfade, die Suche nach der Cura-Definition und der Austauschordner sind repariert (`ca18e5a8`, `8c38d193`); jeder Schritt ist einzeln geprüft, die **Kette als Ganzes** nicht — dazu braucht es zwei echte Flatpaks. **Gebaut, Bestätigung offen** |
| CA-Zertifikate auf macOS | Der erste Kundenbericht aus dem Feld (27.08.2026) | **Rückfall gebaut, Feldbestätigung offen:** Das macOS-Paket bringt certifis CA-Satz ausdrücklich mit und setzt ihn vor dem ersten Netzzugriff, sofern keine Firmenvorgabe besteht. Es fehlt ein echtes Paket auf einem Mac; dort *Hilfe → Nach Updates suchen* drücken |
| AppImage erscheint erst mit der nächsten Version | Linux durfte nicht updaten, und Windows fragte sechsmal (28.08.2026) | **Entschieden, Robert 28.08.2026:** AppImage und Flatpak werden ab der nächsten Version ausgeliefert; das Archiv bleibt ein Bauartefakt. Bis dahin bleibt die aktuelle Download-Seite unverändert |
| `rtree` liegt als Überrest auf den Entwicklungsmaschinen und macht vier Tests rot | Der Verkaufsstart und die vorerst entfallene Testphase (28.08.2026) | je Maschine einen Befehl: `python -m pip uninstall -y rtree`. Am 24.08. aus `pyproject.toml` entfernt und durch `geom/enclosure.py` ersetzt, seither auf der Sperrliste — eine Deinstallation reist aber in keinem `git pull` mit. Auf einer der drei Maschinen am 28.08. erledigt |
| 3D-Maus — festschreibbar und lizenzrein, es fehlt nur noch das Gerät | Eine Kundenanfrage aus dem Dentalbereich (30.08.2026) | **nur noch Roberts Gerätekauf (~150 €)** und den Grundsteuerungs-Abschluss. Falle 1 ist gemessen (15/53, frische venv, Messlatte vorab): pyspacemouse 2.1.0/easyhid 0.0.10/cffi exakt pinbar, Lizenzkette MIT/MIT/MIT-0 plus hidapi mit wählbarem BSD — kein GPL. Verschärfung gefunden: `import pyspacemouse` bricht ohne Gerät schon beim Import (easyhid lädt `hidapi.dll` auf Modulebene, die DLL liegt nicht im Wheel) → drei Bauauflagen stehen fest: DLL mitliefern (BSD gewählt, Lizenzliste + Spec), Import hinter den deferred-Zaun in brep-Bauart (meldet sich ab, wenn es fehlt), und der `open()`-Beweis fällt ehrlich erst mit dem Gerät |
| Resin Stufe 1 — entschieden: bauen als nächste Serie | Eine Kundenanfrage aus dem Dentalbereich (30.08.2026) | den Serienstart nach der Panels-Welle (D1–D12) — Weg B mit zwei beratschlagten Präzisierungen (zwei generische Geräte, B4 in Stufe 1); Paketschnitt bei Start |
| Die Zusagen aus der Antwort an den Kunden | Eine Kundenanfrage aus dem Dentalbereich (30.08.2026) | den Verkaufsstart — die Mail ist seit dem 30.08.2026 versendet, spätestens zum 01.11.2026 bekommt der Kunde die zugesagte Nachricht |
| `website/dl/` sammelt jede je gebaute Fassung | Der Download-Ordner sammelt jede je gebaute Fassung (30.08.2026) | eine Produktentscheidung von Robert: alte Pakete behalten (Rollback-Archiv) oder auf die angebotene Fassung eindampfen — lokal 11 GB in 40 Dateien ab 0.1.1, und was davon auf dem Server liegt, ist noch nicht gezählt |
| Das Update-Fenster zeigt die Punkte ohne ihre Gruppen | Das Update-Fenster verliert die Gliederung auf dem Transport (30.08.2026) | d3s Paket — `groups` in die `version.json` (synchron gekappt), `updates.Release` liest sie, der Dialog gliedert wie der Verlaufs-Dialog; Review und Alt-Client-Messung bei der Freigabe |
| Die Grundsteuerung verlangt CAD-Gewohnheiten | Die Grundsteuerung soll sich wie im Slicer anfühlen (30.08.2026) | noch zwei Pakete: P6 (aufs Bett setzen) und P9 (Züge bündeln), beide frei — P1/P3/P5/P7/P8 fertig, P2 durch P1 miterledigt, P4 gestrichen; Review je Paket bei der Freigabe |
| Panels und Dialoge sollen den Leitsatz einlösen | Alle Panels und Dialoge aus Kundensicht (30.08.2026) | noch fünf Pakete: D3, D5, D6, D8, D10 — neun sind zu (zuletzt D9, D11, D13, D14a/b), dazu der Skeletteditor-Lader auf Roberts Wort; Review je Paket |
| Neun Z-Pakete des Zeichenmodus | Der Zeichenmodus und der Viewport bekommen ihre Durchsicht (30.08.2026) | die Abarbeitung — Z1 ist zu (`20838a37`: Escape kostet nichts mehr), dann Maß-ändern und die Ausgänge; Review je Paket |
| Neun V-Pakete des Viewports | Der Zeichenmodus und der Viewport bekommen ihre Durchsicht (30.08.2026) | die Abarbeitung — acht von neun sind zu (zuletzt V8, `f1ed8050`: der Hinweis ist das bestimmende Maß fürs Panel), nur V6 bleibt (3a — ihre Hand wurde frei, 72s nicht); Review je Paket |
| Ø-Bedingung im Kern | Der Zeichenmodus und der Viewport bekommen ihre Durchsicht (30.08.2026) | eine eigene Format-Entscheidung nach Z7a — Durchmesser als echte Bedingungsart bis in die Projektdatei, mit Migrationsblick |
| Dreizehn G-Pakete des Designs | Design und Anmutung bekommen ihre eigene Durchsicht (30.08.2026) | **die vollständige Abarbeitung — Roberts Order (30.08.2026): das ganze Dokument, alle 40 Befunde**, nicht nur die kritischen. Die style.py-Pakete G1/G2/G3/G7 als Serie in einer Hand (72), G11 bei 50, G12 dockt an D11 (15); je Paket Belegbild vorher/nachher und Review; **Folge der Beleuchtungs-Fixes: `app/images/` vor dem nächsten Paketbau neu erzeugen** |

---


## P0 — Skelett

### Grundgerüst
- [x] Repository, Paketstruktur nach §8, `pyproject.toml`, Werkzeuge
- [x] Test: `core` ohne installiertes Qt importierbar
- [x] Test: keine deutschen Stämme in Bezeichnern (§4.1)
- [x] `core/types.py` — Verträge aus §9 vollständig, noch ohne Umsetzung
- [x] `core/errors.py` — Hierarchie aus §33.1, jede Ausnahme mit `suggestions`
- [x] `core/units.py` — `EPS_GEOM`, `EPS_DISPLAY`, `EPS_MATCH` (§11.2)
- [x] Startsatz Druckerprofile als Datentabelle (§38)
- [x] Protokollierung nach §33.2

### Register
- [x] `@register_op` mit allen Feldern aus §10
- [x] Erzeugung: Menü, Kontextmenü, Palette, CLI, Tool-Schema, Doku
- [x] Registerkonsistenztest (§35)

### Szene und Auswertung
- [x] `Scene`, `SceneObject`, `Parameter`, `Fit`, `Transaction`
- [x] Op-DAG mit `in`/`out`, lineare Darstellung
- [x] Auswertung als reine Funktion (§15.1), Test: zweimal = identisch
- [x] Objektzahländerung hält an statt zu raten (§15.2)
- [x] Undo/Redo auf Transaktionsebene (§15.5)
- [x] Abbruch ohne halb angewandte Ops (§15.6)
- [x] Cache über Op-Hash, RAM-Grenze, Plattencache — der Mesh-Codec des
      Plattencaches kommt mit dem Geometriekern (P2)

### Parameter
- [x] Ausdrucksgrammatik und eigener Auswerter — **kein `eval`** (§13, §32)
- [x] Zyklenerkennung
- [x] Test: alles außerhalb der Grammatik wird abgelehnt

### Projektdatei
- [x] Container `.p3d` nach §16.1
- [x] `format_version`, Migrationsgerüst, erste Beispieldatei
- [x] Prüfsummen, keine absoluten Pfade
- [x] Autosave und Absturzwiederherstellung (§38)

### Eingangsstufe
- [x] Op `load` mit den sechs Schritten aus §17.1
- [x] Einheitenheuristik mit Rückfrage über `ctx.ask`
- [x] Import-Obergrenzen mit klarer Meldung (§32)

### Testkorpus
- [x] `tests/data/` nach §34 anlegen, `README.md` mit Erwartungswerten — der
      Rest kam mit den Bausteinen aus P2/P3 nach, siehe „Referenzkorpus und
      Passungen vervollständigt"
- [x] Alle Dateien selbst erzeugt oder frei lizenziert (`make_corpus.py`)

### Oberfläche
- [x] Grundfenster nach §2.5, drei Zonen, rechter Bereich ausblendbar
- [x] Viewport (Grundnavigation, drei Schemata §2.9)
- [x] Objektbaum, Parameterleiste, Verlauf
- [x] Statusleiste mit Maßen, Auswahl, Fortschritt, Abbrechen
- [x] Startbildschirm mit Ablagefeld und zuletzt geöffneten Projekten (§2.3)
- [x] Ziehen und Ablegen auf Fenster, Viewport, Objektbaum
- [x] Übersetzungsgerüst, deutsche und englische Version

### CLI
- [x] Befehle aus dem Register, `ask` als Abfrage, `progress` als Zeile

### Abschluss P0
- [x] Lizenzprüfung gegen Freigabeliste (§36) — `tests/test_licences.py`,
      Freigabeliste in `app/core/knowledge/data/licences.toml`,
      Drittlizenzen in `THIRD-PARTY-NOTICES.md`
- [x] Lizenzentscheidung getroffen, Name entschieden (§37.1) — **Solidon**,
      proprietär (RS Digital, 2026), Bausteinbibliothek und Testkorpus MIT;
      alles Namensbezogene steht in `app/branding.py`
- [x] Alle Abnahmekriterien P0 aus §40 grün — `tests/test_acceptance_p0.py`
      (das Kontextmenü am Merkmal ist mit P3 belegt, Objekt-Kontextmenü steht)

---

## P1 — Sehen und Messen
- [x] Darstellungsmodi, Schattierung, Kameravoreinstellungen (§18.1)
- [x] Schnittebene **mit Capping**, Bildvergleichstest (§18.2) — der Nachweis
      läuft über Geometrie statt Pixel: die geschnittene Hälfte ist wasserdicht
      und hat genau das halbe Volumen, was ein Bild nicht unterscheiden könnte
- [x] Messwerkzeuge, Durchmesser über Feature, Bemaßungen (§18.3) — Abstand mit
      Fang auf Punkte und Kanten, Wandstärke über eigenen Raycast, Bemaßungen
      bleiben stehen; der **Durchmesser** wird mit P3 nicht gemessen, sondern am
      ausgewählten Merkmal abgelesen und in der Statusleiste gezeigt
- [x] Gizmo und Snapping — jede Manipulation erzeugt eine Op (§18.10); die
      Transformations-Ops aus P2 sind dafür vorgezogen, ein Zug wird zerlegt
      und als **eine Transaktion** eingetragen. Fang auf Fläche und Bohrungsachse
      kam mit P3 als Op `align_to_feature` (`core/geom/align.py`)
- [x] Paletten und Alternativkodierung, Test auf Farbunabhängigkeit (§19.1)
- [x] Tastaturnavigation, Befehlspalette (§19.2)
- [x] Helles und dunkles Thema, HiDPI (§19.3)
- [x] Leistungsziele Viewport (§31) — `tests/test_performance.py` misst gegen
      die absoluten Ziele und gegen den letzten Lauf auf derselben Maschine
      (Regressionsschwelle 25 %); die Bildrate im Viewport selbst misst VTK,
      nicht die Suite

## P2 — Operationen manuell
- [x] Reparatur-Ops gegen `broken_open`, `degenerate` — Löcher in Dreiecksgröße
      werden geschlossen, eine fehlende Wand wird ehrlich als offen gemeldet
- [x] Transformationen, Ausrichten (in P1 vorgezogen), druckoptimal orientieren
      als Normalen-Heuristik — der Befund weist sie als solche aus
- [x] Boolesche Ops mit Rückfallkette §17.2, Stufe und Startwert in der Op —
      alle vier Stufen einzeln erzwungen und geprüft
- [x] Bohrungs-Ops, Schneiden, Anordnen, Kollisionsprüfung
- [x] Export nach §29 einschließlich Namensschema und Exportprüfung
- [x] Orientierung vorerst als Normalen-Heuristik, in P3 ersetzt
- [x] Fehlerdarstellung als Vorschlag (§2.7) für alle Geometriefehler — jede
      Ausnahme trägt Vorschläge, die Oberfläche zeigt sie als Knöpfe
- [x] **Weg 1 aus §2.2 als Ende-zu-Ende-Test** — `tests/test_way_one.py`

## P3 — Wahrnehmung und Schichtanalyse
- [x] Feature-Erkennung (§21.1) gegen `plate_holes`
- [x] Provenienz-IDs und Zuordnung, `plate_holes_twin` als mehrdeutig — die
      Transformations-Ops melden ihre Bewegung (`OpResult.transform`), die
      Zuordnung nimmt die alten Merkmale erst mit und vergleicht dann; ohne das
      verlor jede Drehung alle Namen. Nachweis: zehn Ops hintereinander
- [x] Verwaisungsdialog über `ctx.ask`, Prüfung beim Öffnen — `core/scene/orphans.py`
      prüft beim Öffnen jeden Merkmalsverweis einmal, schreibt die Antwort in die
      Datei und fragt sie darum nicht bei jedem Lauf erneut
- [x] Steckbrief (§23)
- [x] Analysekarten (§18.4), Klick auf Warnung fährt die Kamera hin — sieben Karten
      in `core/perceive/maps.py`, Legende mit Zahlenbereich und Herkunft
- [x] Feature-Overlay mit Kontextmenü (`applies_to`) — Beschriftungen im Viewport,
      Merkmale als Kinder im Objektbaum, Kontextmenü aus dem Register.
      Anklicken und Auswählen stehen.

      **Die Begründung hier war überholt** (nachgesehen am 14.08.2026): Die
      Mauszeiger-Ereignisse fehlen nicht mehr. `viewport._note_pointer`,
      `_look_under_pointer` und `_forget_pointer` stehen, mit einem
      entprellenden Zeitgeber und Suche über den Tiefenpuffer statt über einen
      Aktor-Pick. Was das Überfahren **zeigt**, ist allerdings der Mauszeiger
      („feature" statt „select") und keine Hervorhebung am Merkmal selbst.
      Das ist keine halbe Umsetzung, sondern eine andere: Ein Umfärben je
      Zeigerbewegung ginge über den Aktor, und genau den meidet die Stelle aus
      Kostengründen. Wer die Hervorhebung will, bekommt sie über
      `highlighted_faces` — dieselbe Bahn, die die Auswahl seit dem 13.08.
      benutzt — und bezahlt sie mit einem Aktor-Update je Ruhepause.
- [x] Passungen anlegen und prüfen (§14)

### Schichtanalyse (§22)
- [x] `core/slice`: Ebene-Mesh-Schnitt, Konturverkettung — mit Shapely statt
      Clipper2, gleiche Aufgabe, schon in der Freigabeliste
- [x] Kennzahlen je Schicht: Fläche, Überhang, Inseln, Brückenweite, Minimalbreite
- [x] Test gegen analytisch bekannte Körper (Würfel, Zylinder, Kegel) auf 1 %
- [x] `island_tower.stl` wird erkannt
- [x] Orientierungssuche über hunderte Kandidaten, mit Startwert, abbrechbar
- [x] Analysekarten Überhang und Stützbedarf auf echte Werte umstellen — der
      Stützbedarf entscheidet über die Schichtanalyse, nicht über eine
      Normalenregel; die Säulenhöhe kommt aus demselben Raster wie die Wandstärke
- [x] Schichtenvorschau im Viewport (§18.10), ehrlich beschriftet
- [x] Herkunft jeder Kennzahl ausweisen (`internal`), nie mit G-Code vermischt —
      Legende und Prüfbericht weisen sie aus
- [x] Leistungsziele §31 für die Schichtanalyse — **alle drei im Ziel**,
      gemessen in `tests/test_performance.py` und am 29.08. zusätzlich in einer
      warmen Serie. Die Orientierungssuche liegt unter 20 s. Die
      Wandstärkenkarte fiel durch wiederverwendete Abtastfelder von 3,10 auf
      1,43–1,48 s. Der native Kern schneidet, gruppiert und verkettet selbst;
      dazu entfallen doppelte Sorts, Konturkopien und sicher unnötige
      Brückenmessungen. Die ganze Schichtanalyse fiel von 1,05 s ohne Kern auf
      331–355 ms bei 327 680 Dreiecken und 288–299 ms bei exakt 200 000
      (Median 292 ms). Suite und Paketier-Job bauen den Kern auf jeder
      Plattform, die Spec fordert und verpackt ihn — der frühere
      Auslieferungsrest ist geschlossen

      **Historischer Zwischenstand vom 14.08.2026:** Damals stand die
      Wandstärkenkarte bei **4,30 s** — auch allein gefahren, ohne
      Leistungsdatei davor. Die Orientierungssuche lag mit 14,8 s im Ziel, die
      Schichtanalyse bei 1,07 s. Die aktuellen Zahlen stehen im Absatz darüber.

      **Dabei fiel eine verwaiste Messmarke auf, und sie ist verworfen.**
      `subdivide_surface` meldete das 3,54-fache seines Bestwerts (1 956 ms
      gegen 537 ms) und riss damit die Regressionsschwelle — isoliert genauso
      wie im vollen Lauf. Es war keine Verlangsamung: Commit `43afb51` hat am
      13.08. den *Messgegenstand* getauscht („der Leistungstest aus P16.2 maß
      ein Verfahren, das es nicht mehr gibt") und dort schon notiert, was
      seither herauskommt — 1 778 ms und 1 480 ms von 3 000. Die alte Marke
      stand unter demselben Namen weiter in `tests/.performance.json`, und der
      Wächter verglich zwei verschiedene Rechnungen miteinander. Der Docstring
      von `measure()` sagt den Fix wörtlich vorher: „die Marke fällt mit einer
      Begründung im Commit, nicht stillschweigend beim nächsten Lauf" — genau
      das war unterblieben. Marke gestrichen, der nächste Lauf setzt sie neu.
      Die Datei ist gitignored, also gilt das für diese Maschine; wer den Test
      anderswo laufen lässt, fängt ohnehin bei null an

      **Profiliert am 20.08.2026, und das Register nannte die falsche Stelle.**
      Dort stand „was jetzt oben liegt, ist `_plane_segments`". Gemessen liegt
      oben, was der Docstring des Tests seit je sagt — der Polygonaufbau:

      | Stelle | eigene Zeit | Anteil |
      |---|---|---|
      | `shapely.polygonize` (400 Aufrufe, einer je Schicht) | 446 ms | 36 % |
      | `_plane_segments` | 212 ms | 17 % |
      | `shapely.linestrings` | 51 ms | 4 % |
      | `argsort` (2 Aufrufe) | 50 ms | 4 % |

      Gesamt 1256 ms auf 328 000 Dreiecken bei 0,2 mm. `polygonize` ist damit
      mehr als das Doppelte von `_plane_segments`, und es ist ein GEOS-Aufruf:
      Von Python aus bleibt nur, ihn seltener oder mit weniger Daten zu rufen.
      Das bestätigt den Satz von damals — „braucht einen kompilierten Kern,
      keine weitere Python-Idee" — und nimmt der Registerzeile ihre Aussage.

      **Eine Python-Idee war doch noch drin, und zwar die billigste Sorte.**
      Die vierte Zeile der Tabelle: `_plane_segments` suchte die zwei
      kreuzenden Kanten je Dreieck mit `argsort(~crossing, axis=1)`. Zwei
      Zeilen darüber hatte `keep` gerade dafür gesorgt, dass **genau zwei**
      Kreuzungen übrig sind — und wo die Zahl feststeht, ist ein Sort über drei
      Spalten Arbeit für nichts. `np.nonzero(crossing)[1].reshape(-1, 2)` gibt
      dieselben Spalten, zeilenweise aufsteigend. Gemessen an 600 000 Zeilen:
      **50,9 ms gegen 11,5 ms**, und im Profil fällt `_plane_segments` von
      313 auf 276 ms.

      Die beiden anderen `argsort` in der Datei bleiben: Sie sortieren nach
      Schicht und nach Knoten, und dort ist die Reihenfolge das Ergebnis und
      nicht ein Nebenprodukt.

      Was das §31-Ziel angeht, ändert es nichts — drei Prozent von 1256 ms sind
      keine 300. Der Punkt bleibt offen, und er wartet weiter auf dieselbe
      Entscheidung.

## P4 — Agent auf Säule C
- [x] `LLMBackend`, Schlüssel im Schlüsselbund, lokal über Ollama — kein
      Hersteller-SDK, der Transport ist austauschbar, deshalb läuft die ganze
      Schicht in der Suite ohne Netz
- [x] Kontextaufbau nach §26.1
- [x] Werkzeuge nach §26.2 einschließlich `ask_user` und `find_part` — die Ops
      kommen aus dem Register, `find_part` antwortet bis P5 ehrlich, dass die
      Bibliothek leer ist
- [x] Vorschlag = eine Transaktion, Differenzansicht, Übernahme
- [x] Chat-Transaktions-Kopplung (§26.3), verworfene Beiträge ausgegraut
- [x] Herkunftsvermerke (§26.4)
- [x] Agenten-Suite mit 15 Anfragen zu Säule C, davon 3 mehrdeutig —
      `tests/agent_cases.py`. Ohne Modell prüft die Suite, was die Schicht
      garantiert (Kontext, eine Transaktion, Rückfrage kommt an, Schemaprüfung
      vor der Rechnung); die Quote gegen ein echtes Modell misst
      `tools/run_agent_suite.py` und braucht einen Schlüssel
- [x] Regelsammlung §39 als Daten mit Version und Änderungsverlauf; jede
      Transaktion hält die Version fest
- [x] Dateiformat 2: der Chat liegt im Projekt, mit Umstellungsschritt und
      Beispieldatei je Version

## P5 — Bausteinbibliothek
- [x] `@register_part`, `PartFn`, `PartResult` — dazu Version und
      Änderungsverlauf je Baustein, und die Angabe, ob er Material wegnimmt
- [x] Normteiltabelle als Daten, nicht im Code — `data/standards.toml`
- [x] Dreizehn Bausteine (§24.1) mit Parameterbereichstests — der Test läuft
      über das Register, ein neuer Baustein ist ab der Deklaration abgedeckt
- [x] `to_scad()` je Baustein — als Ausgabeformat, ehrlich beschriftet: die
      Werte stehen zum Nachlesen darin, der Körper ist das exakte Netz
- [x] Katalog mit automatisch gerenderten Vorschaubildern (§24.3) — als SVG aus
      dem Baustein selbst, ohne 3D-Kontext und ohne neue Abhängigkeit
- [x] `parts_version` in der Projektdatei, Änderungsverlauf je Baustein (§24.4)
- [x] Beim Öffnen: geänderte benutzte Bausteine namentlich melden
- [x] Eigene Bausteine aus dem Nutzerordner (§24.5), im Katalog gekennzeichnet
- [x] Test: eigener Baustein reist nicht mit der Projektdatei
- [x] Nachweis: kein Kernpfad benötigt OpenSCAD — `tests/test_parts.py` baut
      alle dreizehn gegen manifold3d durch

## P6 — Säule A
- [x] Agent erzeugt Op-Listen aus Bausteinen und Parametern — dazu die
      Primitive aus §25 (`create_box`, `create_cylinder`, `create_sphere`),
      ohne die eine leere Szene keinen Anfang hat, und `at_feature`, um einen
      Baustein an ein erkanntes Merkmal zu setzen
- [x] OpenSCAD als Rückfallebene mit Quelltextprüfung (§32) — `include`, `use`,
      `import` und `surface` nur relativ und unterhalb des Arbeitsordners,
      eigener Ordner je Lauf, Zeitlimit, getrimmte Umgebung. Der Nachweis ist,
      dass abgewiesener Quelltext **keinen Prozess startet**
- [x] Messung: Bausteinnutzung, Parameternutzung — fünfzehn Anfragen zu Säule A
      in `tests/agent_cases.py`, damit dreißig insgesamt (§35); die Quote gegen
      ein echtes Modell zählt `tools/run_agent_suite.py --pillar A`
- [x] **Weg 2 aus §2.2 als Ende-zu-Ende-Test** — `tests/test_way_two.py`

## P7 — Slicer-Rückkopplung und Kalibrierung
- [x] G-Code auswerten (§28.1) als Gegenprobe zur internen Schätzung — Druckzeit,
      Material, Schichtzahl und das **gemessene** Stützvolumen aus den
      Typ-Kommentaren und der E-Achse. Was nicht in der Datei steht, bleibt
      unbekannt statt null
- [x] Abweichung über 15 % erscheint als Befund im Prüfbericht — und die
      Schätzung wird dabei nicht ersetzt, beide bleiben stehen (§28.2)
- [x] Herkunft der Kennzahlen im Bericht ausgewiesen (intern / G-Code)
- [x] Toleranz-Testkörper und Varianten-Generator (§28.3) — Passungsleiter,
      Wandstärkenleiter und Überhangfächer als Bausteine mit eigener Gruppe;
      der Varianten-Generator dreht einen Projektparameter durch und ordnet die
      Ausführungen an, ohne den Stapel anzufassen
- [x] Materialprofile kalibrierbar, Durchschlag auf bestehende Projekte — die
      Werte landen im Nutzerprofil, die mitgelieferten Startwerte bleiben
      unberührt, und weil Toleranzen Verweise sind, rechnen alte Projekte danach
      mit den neuen Werten
- [x] **Druckeinstellungen in der Anwendung** (§29) — `PrintSettings` hält
      Schichten, Wände, Füllung, Temperaturen, Kühlung, Geschwindigkeiten,
      Stützen, Haftung, Rückzug und Filament samt Farbe; aufgelöst aus
      Qualitätsstufe, Material und Drucker. Der Dialog zeigt vorn acht Werte,
      dahinter alles nach Gebieten
- [x] **Hinweg zum Slicer** (§29) — `export/handover.py` schreibt das Profil,
      ruft den Slicer im Konsolenmodus und liest den G-Code zurück. Drei
      Familien über `export/slicer_keys.py`: PrusaSlicer und SuperSlicer als
      eigenständige ini, Orca/Bambu/Elegoo als Prozess-JSON auf ein
      Systemprofil gelegt, CuraEngine über `-s`
- [x] **Einstellungen aus der Geometrie** (§29) — `slice/advise.py` schließt
      aus Schichtanalyse, Material und Maschine auf Stützen, Plattenhaftung,
      Mindestschichtzeit, Linienbreite und Außenwandtempo. Jeder Vorschlag mit
      Begründung, übernommen wird auf Klick. Was kein Wert behebt, wird ein
      Befund statt eines Vorschlags
- [x] **Maschinen- und Prozessprofil des Slicers wählbar** (§29) —
      `export/slicer_profiles.py` liest den Bestand des installierten Slicers,
      löst die Erbkette der Verträglichkeit auf und ordnet über `printer_model`,
      Düse und `default_print_profile` selbst zu. Die Auswahl steht im Dialog
      für den Fall, dass jemand abweichen will; gelesen wird im Hintergrund
- [x] **Volumenstrom als Grenze** (§29) — `max_flow` je Material, gegen
      Schichthöhe mal Bahnbreite mal Tempo geprüft. Darüber Düse heißer,
      und wo die Maschine am Anschlag ist, stattdessen langsamer. Die Regel
      rechnet gegen den Stand *nach* den übrigen Vorschlägen, und die Zahl
      reist als `filament_max_volumetric_speed` zum Slicer mit
- [x] **Druckeinstellungen im Projekt** (§29) — `format_version` 4 mit
      Migration; `None` heißt „noch nichts entschieden", nicht „alles null".
      Beispieldatei `example_v4.p3d` eingecheckt
- [x] **Druckdatei speichern** — was der Slicer schreibt, lag im Arbeitsordner
      und verschwand mit ihm. Jetzt speicherbar, mit Ordner und Name des
      Projekts als Vorschlag
- [x] **Vorschläge einzeln wählbar** — vorbelegt angehakt, aber abwählbar;
      alles-oder-nichts hieße, für einen unpassenden Vorschlag die übrigen
      mit aufzugeben
- [x] **Nur die gewählte Plattenhaftung bekommt Maße** — Skirt, Brim und Raft
      sind Maße ihrer Art, keine Schalter. Vorher lief unter jedem Teil ein
      Raft mit, auch bei eingestelltem Skirt
- [x] **3MF als Baugruppe schreiben** (§20, §29) — `threemf.write_assembly`
      legt mehrere Körper in eine Datei, ein `object` je Teil. Der Slicer
      bekommt damit einen Druckauftrag statt einer Handvoll Teile, über deren
      Zusammengehörigkeit er selbst entscheiden müsste
- [x] **Farbgruppen als Extruderzuordnung** (§20) — `merge_slots` legt die
      Materialslots aller Teile über Name und Farbe zusammen; die Reihenfolge
      des Ergebnisses ist die Extruderbelegung. Ohne das fragte der Slicer
      nach drei Filamenten für einen einfarbigen Druck aus drei Teilen
- [x] **Gegenprobe statt einmaliger Prüfung** (§28.2) — `handover.verify`
      liest die Konfigurationskommentare der erzeugten Datei und meldet, was
      der Slicer anders übernommen hat. Damit prüft sich jeder Slicer selbst,
      auch einer, den beim Bauen der Tabelle niemand vorliegen hatte
- [x] **Jeder Wert in das Profil, in das er gehört** (§29) — die Orca-Familie
      führt Prozess und Filament getrennt und übergeht einen Wert im falschen
      Profil stillschweigend. Achtzehn taten das: beide Düsen- und beide
      Betttemperaturen, die ganze Kühlung, alle Filamentwerte und der Rückzug.
      Sie standen im Prozessprofil und kamen nie an — gedruckt wurde mit dem,
      was zuletzt im Slicer stand. `slicer_keys.Entry` trägt jetzt die
      Profilart, `handover` schreibt zwei Dateien und lädt das Filament über
      `--load-filaments`. Der Rückzug geht als `filament_*`-Entsprechung, damit
      Solidon nicht ins Maschinenprofil hineinredet — das passt auch zur
      Herkunft, denn er kommt aus dem Material. `test_every_orca_setting_sits_in_the_profile_it_claims`
      prüft die Zuordnung gegen den Bestand eines installierten Slicers und
      wäre am alten Stand mit achtzehn Verstößen rot gewesen
- [x] **Filamentprofile des Slicers lesen** (§29) — `slicer_profiles` kennt
      jetzt auch `filament/`, löst mit `resolve_values` die Erbkette auf (beim
      transluzenten Elegoo-PETG 55 Werte aus vier Dateien, wo die oberste drei
      nennt) und wählt über `match_filament` die Grundausführung des
      eingestellten Materials vor. Der Dialog zeigt sie zur Auswahl, `handover`
      legt die Solidon-Werte darauf. Gelesen werden Filamente nur auf
      Verlangen: sie vervielfachen den Bestand, 5962 gegen 3887.
      `profile_differences` meldet, wo Solidons Tabelle und der Hersteller
      auseinandergehen — 240/80 °C gegen 255/70 °C beim transluzenten PETG —,
      übernimmt aber nichts davon
- [x] **Die Stellschrauben, die für Passungen zählen** (§29) — `wall_generator`,
      `precise_outer_wall`, `ironing`, Brückentempo und zwei Beschleunigungen,
      mit Vorgaben je Qualitätsstufe. Dazu drei Regeln in `advise.py`:
      schmalste Stelle unter drei Linienbreiten schaltet auf Arachne (mit
      fester Linienbreite bleibt dort eine Lücke, die nur Lückenfüllung
      schließt — der Bruch eines 1,1-mm-Federarms), Passungen holen die genaue
      Außenwand und bremsen auf 2000 mm/s², Überhänge deckeln das Brückentempo
      auf das der Außenwand. Elefantenfuß und Lochkorrektur blieben draußen:
      für den ersten gibt es `compensate_elephant_foot` in der Geometrie, die
      zweite hat bisher gar keinen Anwender — beides zu übergeben hieße,
      doppelt zu rechnen
- [x] **Einstellungen je Teil** (§29) — `AssemblyPart.settings` trägt, was nur
      für ein Teil gilt, und `write_assembly` schreibt dafür
      `model_settings.config`. `advise.for_part` entscheidet die Plattenhaftung
      je Teil aus Bounding-Box und einem Schnitt 0,2 mm über dem Boden: ein
      Körper auf drei schmalen Armen hat eine große Bounding-Box und kaum Halt.
      Damit bekommt die Streuscheibe ihren Brim und keiner der zwölf Behälter.
      Nebenbei kamen damit auch die **Objektnamen** erstmals im Slicer an — sie
      standen im `name`-Attribut des Standards, das die Orca-Familie selbst nie
      schreibt und folglich nicht liest; eine Baugruppe erschien als
      „Object 1, Object 2"
- [x] **Platten aus Materialgruppen** (§25, §29) — `plates_by_material`
      schlägt ein Filament je Platte vor, `check_adhesion_clearance` rechnet
      den Haftungsrand mit (zwei Körper können Luft haben und ihre Brims
      trotzdem ineinanderlaufen — daran war die erste Deckelplatte des
      Gewürzsets zu eng), und `check_filament_changes` nennt den Preis zweier
      Filamente auf einer Platte, statt ihn zu verbieten: 110 gemeinsame
      Schichten und 220 Wechsel, wenn ein 68-mm-Behälter neben einem
      22-mm-Deckel steht. Die Spülmenge in Gramm bleibt draußen, sie steht im
      Profil des Slicers
- [x] **Das Gewürzset aus Solidon heraus gebaut** — die Probe auf die fünf
      Stufen, gegen das von Hand entstandene Projekt. Plattenvorschlag,
      Profilzuordnung und die Werte stimmten; die Automatik traf sogar die
      bessere Entscheidung als die Handarbeit (Brim gehört unter die
      Deckelbasis mit 282 mm² Standfläche, nicht unter die Streuscheibe mit
      516). Gefunden wurden dabei drei Dinge: das Regal-STL liegt nicht
      zentriert und stand über den Bauraum, `nil` wurde als Abweichung vom
      Herstellerprofil gemeldet statt als Nicht-Aussage, und `arrange_bed`
      kennt den Haftungsrand nicht. Die ersten beiden behoben, das dritte
      unten
- [x] Anordnung und Plattenhaftung zusammenbringen — der Dialog des Anordnens
      öffnet mit dem Abstand, den die Haftung verlangt (zweimal den Rand),
      vorbelegt und änderbar. Die Operation kennt die Druckeinstellung
      weiterhin nicht und soll es nicht; das Fenster kennt beide Seiten.
      **Vorher war das folgenlos**, siehe den nächsten Punkt: die Anordnung
      kam beim Slicer gar nicht an
- [x] Plattenvorschlag angeboten — `arrange_bed` trägt jetzt den Umschalter
      *Nach Filament trennen*, nicht eine zweite Operation daneben. Die
      Plattengrenze gilt der ganzen Szene; sind die Platten aufgebraucht,
      teilt sich die letzte Gruppe die letzte, wie `arrange_on_bed` es
      innerhalb einer Gruppe hält
- [x] Bügeln aus der Passung abgeleitet — `advise` bekam ein `has_fits: bool`,
      obwohl das Dokument die Arten führt. Jetzt reicht der Dialog sie durch,
      und nur `flush` löst den Vorschlag aus: bei Schiebesitz, Presssitz oder
      Gewinde wäre Bügeln verlorene Zeit auf einer Fläche, die nichts berührt
- [x] **PrusaSlicer läuft Ende zu Ende** (2.9.6, am 07.08.2026: 1,01 MB
      G-Code, 22,6 g, 110 min). Beide Funde davor waren unsichtbar, solange
      das Programm fehlte: die Programmsuche ging eine Ebene zu flach für
      `Prusa3D\PrusaSlicer\`, und die Bettform stand von 0 bis 256, während
      Solidon um den Ursprung rechnet — „All objects are outside of the
      print volume", ohne dass irgendwo stand, warum
- [x] **Cura läuft Ende zu Ende** (5.13.0). Die Kette hatte fünf Stufen:
      - [x] Der Aufruf ging an `UltiMaker-Cura.exe`, also an die Oberfläche.
            Die Kommandozeile hat nur `CuraEngine.exe` daneben
      - [x] `CuraEngine` liest **kein 3MF** — die 3MF-Seite sitzt im Frontend.
            Für Cura schreibt die Übergabe STL
      - [x] `fdmprinter.def.json` als Basis reicht, wenn die Werte mitkommen,
            die es ohne Vorgabe lässt. Gefunden durch Zufüttern, bis der
            Rückgabewert 0 war: Bauraum, Düse, `machine_center_is_zero`,
            `roofing_layer_count`, `flooring_layer_count`. `_cura_base()` sucht
            die Datei unter `share/cura/resources/definitions`
      - [x] **Der Lauf fördert — er sagte es nur nicht.** Der Befund
            „8,6 MB Leerfahrten" war eine Fehldeutung des Kopfes: die Datei
            enthält Bahnen mit Vorschub, und `gcode.extrudes()` bestätigt das.
            `Filament used: 0m` und `MINX:2.14748e+06` sind **Vorlagen**, die
            CuraEngine vor dem Rechnen schreibt und das Fenster nachträglich
            ersetzt; von der Kommandozeile aus bleiben sie stehen. Dasselbe
            gilt für `;TIME:6666` — 111 Minuten für jedes Modell, auch für
            einen halb so hohen Würfel. Solidon liest die Länge jetzt aus der
            E-Achse und die Zeit aus der letzten `TIME_ELAPSED`.
      - [x] **Die Werte erreichten den Extruder nicht.** CuraEngine hält zwei
            Ebenen, und das meiste, was einen Druck ausmacht, liest es vom
            Extruder-Zug. Was nur global stand, wurde von der Vorgabe der
            Definition überschrieben. Dazu zwei Einzelfehler: die erste
            Bahnbreite ist dort ein **Anteil** (0,449 mm wurden zu 0,449 %),
            und Beschleunigungswerte gelten erst mit `acceleration_enabled`.

            Gemessen am 20-mm-Würfel gegen PrusaSlicer, dieselben
            Einstellungen:

            | Stand | Filament | Volumen | Zeit |
            |---|---|---|---|
            | vorher | 748 mm | 1,80 cm³ | 111 min (Vorlage) |
            | jetzt | 1998 mm | 4,81 cm³ | 20,9 min |
            | PrusaSlicer | 1410 mm | 3,39 cm³ | 21 min |
            | Handrechnung | — | rund 3,3 cm³ | — |

            Die Zeit trifft jetzt auf die Minute. Was an Material bleibt, ist
            **Curas Rechnung, nicht Solidons Fehler**: mit `infill_pattern=lines`
            statt `grid` kommen 3,70 cm³ heraus, also neun Prozent neben
            PrusaSlicer — der Rest steckt in Curas Gitter-Muster bei 15 %
            Dichte. Nur auf dem Zug zu setzen ist ebenso falsch wie nur global:
            dann fehlen der Zeitrechnung die Geschwindigkeiten (38,4 min).

## P8 — Erste Veröffentlichung
- [x] Name entschieden, überall durchgezogen — alles Namensbezogene steht in
      `app/branding.py`
- [~] CI-Bauläufe, Signierung und Notarisierung — `.github/workflows/` baut
      Windows, Linux sowie macOS für Apple Silicon und Intel, erst nachdem die
      Suite auf allen drei Plattformen grün ist. Windows wird zu einer
      Setup-Datei (`packaging/solidon3d.iss`, gebaut von
      `tools/make_installer.py`), Linux zu AppImage und Flatpak sowie einem
      internen tar.gz, macOS zu je einem `.pkg`. Alle Werte kommen aus
      `app/branding.py`. Windows unterstützt Azure Artifact Signing per OIDC;
      Anwendung und Setup-Datei werden getrennt signiert und geprüft, der alte
      PFX-Weg bleibt Rückfall. Ohne Azure-Konto oder Zertifikat überspringt sich
      die Signierung mit sichtbarer Warnung. Die Apple-Notarisierung ist als
      gesperrter CI-Schritt gebaut:
      `notarytool` wartet auf Apples Prüfung, `stapler` heftet und prüft das
      Ticket, `spctl` prüft anschließend den Installationsweg. Es fehlen noch
      Apple-Konto, Developer-IDs und die sieben CI-Geheimnisse. Ein grünes Rezept
      ersetzt außerdem keinen Feldlauf der fertigen Pakete. Der Grund,
      der hier einmal stand — es gebe kein Anwendungssymbol —, gilt nicht mehr:
      `app/images/icon/solidon3d.svg` ist die Quelle,
      `tools/make_icon.py` rastert daraus `packaging/solidon3d.ico` und
      `website/icon.svg`, und Installer wie exe tragen es.

      **Die beiden Linux-Formate stehen seit dem 20.08.2026.**
      `tools/make_linux_packages.py` schreibt drei Beschreibungen und baut zwei
      Pakete — und trägt, wie der Windows-Installer, keine eigenen Werte: Name,
      Version, Hersteller und Kennung kommen aus `app/branding.py`. Eine zweite
      Stelle mit einer Versionsnummer ist eine, die veraltet, und hier wollen
      sie drei Dateien gleichzeitig.

      * **AppImage** — eine Datei, die ohne Installation läuft, der kürzeste Weg
        zu „ausprobieren". `AppRun` ist ein Skript und kein Symlink: PyInstaller
        sucht relativ zum eigenen Ort, und ein Link von der Wurzel fände seine
        Bibliotheken nicht.
      * **Flatpak** — der Weg in die Software-Verwaltung, mit Aktualisierung und
        Sandbox. Gebaut wird **um den fertigen PyInstaller-Ordner herum** und
        nicht aus den Quellen: Die Anwendung bringt ihr Python schon mit, und
        ein zweiter Bauweg wäre eine zweite Version, die auseinanderläuft.
      * **AppStream-Metainfo** — ohne sie ist das Flatpak in GNOME Software ein
        Eintrag ohne Text, und ein namenloses Programm installiert niemand. Die
        beiden Lizenzfelder sind auseinandergehalten: `metadata_license` gilt für
        die Beschreibung, `project_license` für das Programm. Sie zu verwechseln
        heißt, sich versehentlich zu verschenken — der Test prüft es.

      **Netzzugang im Flatpak — seit dem 27.08.2026, und die Kehrtwende hat
      einen Anlass.** Hier stand das Gegenteil: `--share=network` sei die
      bequemste Zeile und die falsche, denn ohne Netz gebe es kein Konto, keine
      Telemetrie und keine Frage danach.

      Ein Kunde auf CachyOS hat gezeigt, was das kostet. Sein Fehlerbericht kam
      **per Hand** über Robert, mit dem Satz „Ich kann den Bericht aus der App
      nicht senden: urlopen error"; im Protokoll steht der Grund bei jedem
      Start — `[Errno -3] Temporärer Fehler bei der Namensauflösung`, einmal
      für die Aktualisierungsprüfung und einmal für die Sendung. Was für uns
      eine saubere Sandbox war, war für ihn eine Anwendung, deren Knöpfe nicht
      funktionieren.

      **Und die Zusage hing nie an der Sandbox.** Sie hängt an der Bauart:
      `support.send()` hat genau einen Aufrufer, und der sitzt an einem Knopf
      (`tests/test_support.py` zählt ihn). Windows und macOS haben keine
      Sandbox und dieselbe Zusage seit je. Eine Grenze, die nur auf einer der
      drei Plattformen steht, ist keine Zusage, sondern ein Unterschied — und
      der Kunde erlebt ihn als Fehler. Entscheidung Robert: „jede plattform
      sollte das gleiche haben und alles funktionieren."

      Was sonst drin ist, hat je einen Grund — X11, unter Wayland über
      Xwayland, für Oberfläche und VTK-Viewport, `dri` für OpenGL (§18),
      `home` für die Modelle,
      `org.freedesktop.secrets` für den Schlüssel des Agenten (§26).

      Zwei Stolpersteine sind vorweggenommen, weil sie sonst als Fehlermeldung
      ohne Absender erschienen wären: `appimagetool` ist selbst ein AppImage und
      braucht FUSE 2, das Ubuntu seit 24.04 nicht mehr mitbringt —
      `APPIMAGE_EXTRACT_AND_RUN=1` packt es vorher aus. AppImage und Flatpak
      sind ab der nächsten Version Pflichtausgaben: Fehlt eines, wird der
      Linux-Zweig rot. Wegen `fail-fast: false` laufen Windows und beide
      Mac-Zweige trotzdem fertig; ein halber Linux-Bau wird nicht als
      veröffentlichbar ausgegeben.

      **Geprüft ist, was von Windows aus prüfbar ist**, und das ist mehr als
      nichts: `tests/test_packaging.py` hält die drei Beschreibungen an
      `app/branding.py` (dieselbe Drift-Prüfung wie bei den Handbuchabbildungen),
      liest die `.desktop`-Schlüssel, prüft die Metainfo als XML, verlangt die
      Netzberechtigung und den Aufruf des Werkzeugs durch die CI. Der
      **Bau** selbst braucht Linux und die beiden externen Programme — er bleibt
      ungeprüft wie der übrige Workflow, und aus demselben Grund
- [x] Erstinbetriebnahme (§38) — Sprache und Drucker; übernimmt die eingelegten
      Filamente samt Typ und Farbe aus den erkannten Slicer-Profilen;
      überspringbar, nachholbar, endet beim ersten Import
- [x] Fehlerberichtsdialog mit Container-Anhang — legt einen Ordner an,
      verschickt nichts, und sagt beim Anhängen der Projektdatei, dass die
      Geometrie mitreist
- [x] Drei Beispielprojekte = die drei Hauptwege — erzeugt von
      `tools/make_examples.py`, geprüft von `tests/test_examples.py`, sichtbar
      auf dem Startbildschirm
- [~] Doku, Website, Lizenzhinweise — README mit Erwartungsmanagement, den drei
      Wegen, Paketierung und einem Supportkanal; Lizenzhinweise vollständig.
      Die Adresse in `core/updates.py` steht seit der Subdomain-Entscheidung.
      **Hochgeladen seit dem 08.08.2026**: netcup Webhosting samt Domain
      bestellt, 86 Dateien nach `solidon3d.de/httpdocs`, Auslieferung per
      Host-Header geprüft (Startseite, `en/`, Handbuch, `version.json` als
      JSON — alle 200). Impressum, Datenschutz und Widerruf tragen echte
      Angaben statt Platzhaltern. **Seit dem 08.08.2026 auch verschlüsselt**:
      Let's Encrypt für `solidon3d.de` und `www.solidon3d.de` (ein Zertifikat,
      beide Namen im SAN, bis 06.11.2026), HTTP antwortet für beide mit 301 auf
      HTTPS. Die DNS-Propagation ist durch — beide A-Records auf 188.68.47.33,
      Zone bei netcup. **Seit dem 16.08.2026 sechssprachig**: Startseite,
      Funktionen, KI-Modelle und Handbuch (Seite und PDF) auch auf es, fr,
      it und pt, Sprachwechsler als Aufklappmenü, Regelsammlung mit Versionen
      je Handbuchsprache, Bildschirmfotos neu mit der aktuellen
      Werkzeugleiste. Hochgeladen am 18.08.2026 (297 Dateien), Stichproben
      über alle sechs Sprachen samt Bildern per HTTPS geprüft — alle 200,
      die README bleibt unten (404).

      Ein Umweg war dabei zu vermeiden: Plesk hatte ein **Platzhalter**-
      zertifikat angeboten, und nur dafür verlangt Let's Encrypt die
      DNS-Challenge samt TXT-Eintrag. Für die zwei Namen genügt HTTP-01, und
      das läuft ohne jeden Eintrag. Eine Datei `_acme-challenge.txt` im
      Webspace hilft dabei nicht — eine DNS-Challenge wird im DNS abgefragt.

      **Auffindbar erst seit dem 20.08.2026.** Die Seite stand zwölf Tage
      online und war in keinem Index: `site:solidon3d.de` lieferte null
      Treffer. Der Kopfbereich war seit je vorbildlich — `canonical`,
      `hreflang` über alle sechs Sprachen samt `x-default`, Open Graph,
      `SoftwareApplication` als JSON-LD, und kein einziges Bild ohne
      alt-Text —, aber die zwei Dateien fehlten, die ein Crawler zuerst holt:
      `robots.txt` und `sitemap.xml`, beide 404. Ohne Sitemap muss Google 24
      Seiten über Verweise finden, und eine Domain ohne eingehende Links hat
      keine. Beides erzeugt jetzt `tools/make_seo.py` aus dem Bestand, dazu
      `llms.txt` und die `FAQPage`-Auszeichnung der elf Fragen in allen sechs
      Sprachen; `tests/test_website.py` prüft die Sitemap in beide Richtungen
      und die Auszeichnung gegen das Markup, aus dem sie stammt.

      Drei Funde waren keine Schönheitsfehler. Die Rechtstexte tragen
      `noindex` — sie in die Sitemap zu schreiben, hätte der Search Console
      einen Widerspruch gemeldet, den dann Google auflöst statt wir. Die
      Kopfzeile des Handbuchs verwies auf `index.html` statt auf den Ordner
      und legte damit jede Startseite unter eine zweite Adresse. Und
      `Clear-Site-Data: "cache"` ging bei jeder Antwort mit: ein Übergang vom
      18.08., der den Cache jedes Besuchers vollständig räumte — ausgerechnet
      am Tag mit den meisten Erstbesuchern. Er ist raus, Bilder cachen eine
      Woche, Seiten bleiben auf `no-cache`.

      Zwei Punkte der Durchsicht haben sich beim Nachmessen erledigt: „der
      Text nennt 3D-Druck nicht" stimmte nur für die exakte Zeichenfolge — der
      Wortstamm steht vierzehnmal auf der Startseite, in acht Formen —, und
      ausgehende Verweise auf Autoritätsseiten verbietet die Zusage der Seite
      selbst (`test_the_page_loads_nothing_from_outside`). Beides blieb
      unangetastet.

      Was bleibt, liegt außerhalb: **der Name kollidiert.** Eine Suche nach
      „Solidon3D" liefert SolidWorks, Solid Edge, SolidPrint3D, Solidscape und
      Solidoodle; Google behandelt „Solidon" als Verschreiber. Dagegen hilft
      keine Auszeichnung, nur Zeit und Erwähnungen anderswo.

      Das Postfach `support@solidon3d.de` existiert; SPF, MX und die Annahme
      von außen sind geprüft. Offen bleiben DMARC und der
      Auftragsverarbeitungsvertrag im CCP. Der Zahlungsdienstleister in den AGB
      ist seit dem 08.08.2026 eingetragen (Paddle); Entwurf bleiben die
      Rechtstexte nur noch bis zur fachlichen Prüfung
- [x] Update-Hinweis beim Start — fragt eine Versionsdatei, lädt nichts, und ist
      aus, bis ihn jemand einschaltet
- [x] **Update in der Anwendung** (22.08.2026, Bauplan §37.2 dafür geändert).
      Der Hinweis war eine Zeile in der Statusleiste: Version und Adresse, die
      Adresse als Text und nicht anklickbar, und die nächste Meldung schrieb
      sie weg. Wer nicht im selben Moment hinsah, erfuhr nie davon — und wer
      hinsah, hatte danach eine Adresse zum Abtippen.

      Jetzt: ein Fenster, das sagt, was neu ist (`changelog/<sprache>.md`,
      acht Punkte in Kundensprache statt 97 Commit-Titeln), einen Knopf zum
      Holen mit Fortschritt und Abbrechen, und einen zweiten zum Starten —
      nachdem die SHA-256 gestimmt hat. Die Prüfsummen schreibt
      `tools/make_download.py` in `version.json`; von Hand gepflegt wären sie
      die zweite Stelle, und die zweite Stelle driftet.

      Die Grenze aus §37.2 liegt weiter beim **Auslöser** und nicht beim
      Vorgang: Es lädt nichts von allein, ersetzt nichts im Hintergrund,
      startet nichts ohne Klick. Das Paket kommt nur von demselben
      Rechnernamen wie die Versionsdatei; stimmt die Prüfsumme nicht, wird es
      gelöscht. Unter Linux bleibt es beim Hinweis — Flatpak und AppImage
      ersetzen sich nicht von innen.

## P9 — Säule B und Farbe
- [x] `MeshBackend`, ComfyUI lokal
- [x] Reparaturkette für generierte Meshes
- [x] Materialslots, Attributerhalt über Boolesche Ops und Voxelstufe
- [x] Textur → Slots mit Startwert, 3MF-Export mit Farbgruppen
- [x] **Weg 3 aus §2.2 als Ende-zu-Ende-Test**

Anmerkungen zu P9:

* **Erzeugtes wird Quelle, nicht Operation.** Ein Generator ist keine Funktion —
  dieselbe Anfrage liefert nach einem Modellwechsel etwas anderes. Die Bytes
  liegen deshalb im Projekt wie eine gezogene Datei, und der Stack darüber ist
  der gewöhnliche (`load`, dann `repair`). Prompt und Startwert stehen in der
  Quelle; dafür ist das Dateiformat auf 3 gestiegen.
* **Die Reparaturkette steht im Stack**, nicht im Backend. Sie läuft ohne
  Nachfrage, ist aber ein eigener Schritt — sichtbar im Bericht und
  zurücknehmbar.
* **Beim Schnitt gibt nur her, wer bleibt.** Bei einer Differenz überträgt der
  abgezogene Körper seine Farbe nicht: die Bohrungswand ist eine neue Fläche,
  keine Haut des Bohrers.
* **Die eigene 3MF-Hälfte.** trimesh liest 3MF-Geometrie, gibt aber ein
  einheitliches Grau zurück — Schreiben *und* Lesen der Materialgruppen liegen
  darum in `app/core/export/threemf.py`.
* Die mitgelieferten ComfyUI-Arbeitsabläufe (`app/core/backends/data/*.json`)
  laufen gegen **TripoSG** (MIT für Quelltext und Gewichte). Hunyuan3D lieferte
  dieselbe Güte, aber seine Lizenz nimmt die Europäische Union ausdrücklich aus
  — für eine Anwendung, die hier verkauft wird, ist das ein Ausschluss und
  keine Fußnote. Die Knoten dazu stehen unter
  `app/core/backends/data/comfyui/` und werden aus der Anwendung eingerichtet
  (*Hilfe → Zusätzliche Programme*, dort der Knopf in der Zeile von ComfyUI);
  `python tools/setup_comfyui.py` tut dasselbe von der Kommandozeile. Wer
  andere Knoten installiert hat, ersetzt die Datei — Quelltext ist dafür nicht
  nötig.

## P10 — Auto Split mit Verstiftung
- [x] Trennebene über die Schichtanalyse suchen (§22.3), dann konvexe Zerlegung
- [x] Schnittflächen verschließen, Slots übertragen
- [x] Passstifte mit kalibriertem Spiel, Passungspaare automatisch
- [x] Anordnen und Explosionsansicht
- [x] `oversized.stl` ohne Eingriff druckbar zerlegt

Anmerkungen zu P10:

* **Was eine Trennebene gut macht, ist nicht ihre Größe.** Bewertet werden drei
  Dinge: eine Kontur statt fünf dünner Brücken, ein prismatischer Verlauf (der
  Querschnitt ändert sich über einen Millimeter kaum) und Ausgewogenheit. Die
  Konturzahl wiegt am schwersten — eine Naht, die in mehrere Stege zerfällt,
  ist schlimmer als jede Unwucht.
* **Die konvexe Zerlegung liefert einen Hinweis, kein Ergebnis.** Ihre Hüllen
  nähern den Körper an; ein aus Näherungen zusammengeklebtes Teil wäre ein
  genähertes Teil. Übernommen wird nur die *Position*, geschnitten wird exakt
  mit einer Ebene. Sie wird erst gefragt, wenn keine der abgetasteten Ebenen
  überzeugt.
* **Ein Fund unterwegs:** `_plane_segments` in der Schichtanalyse rechnete den
  Layer-Index aus `heights[1] - heights[0]` — richtig für gleichmäßige
  Schichten, still falsch für die ungleichmäßigen Höhen der Ebenensuche. Jetzt
  über `searchsorted`; die Schichtanalyse ist der Sonderfall.
* **Auto Split ist ein Ablauf, kein einzelner Op.** Pro Schnitt eine
  `split_pinned`-Operation, damit jede Trennebene eine Zahl bleibt, die man
  danach ändern kann. Die Passungspaare entstehen im Ablauf, weil Passungen im
  Dokument leben und die Auswertung eine reine Funktion bleibt (§15.1).
* Die Explosionsansicht verschiebt nur Punkte auf dem Weg in die Anzeige. Was
  der Stack sagt und was exportiert wird, bleibt unberührt.

## Leistung (§31) — Stand nach der Durchsicht

### Die Regressionsschwelle schlägt an, ohne dass etwas langsamer wurde

Gemessen am 14.08.2026, fünf Läufe von `pytest tests/test_slice.py
tests/test_performance.py -p no:randomly` allein auf der Maschine: **zwei von
fünf rot**, und zwar nicht am selben Test — einmal `sketch_solve_200` (125 ms
gegen den Bestwert 94 ms, Faktor 1,33), einmal `blending`. Beide Male war es die
25-%-Schwelle, kein absoluter Zielwert und keine echte Verlangsamung.

**Der Docstring von `measure` beschreibt die Ursache selbst**, und er hat sie
nur halb behoben: Er nennt achtunddreißig Prozent Unterschied allein aus der
Aufrufreihenfolge — `sketch_solve_200` braucht allein 114 ms und hinter
`test_slice.py` 162 — bei einer Schwelle von fünfundzwanzig. Das Merken des
**besten** Werts statt des letzten behebt das Anheben der Marke; dass ein Lauf
unter Fremdlast rot wird, „obwohl nichts langsamer wurde", steht dort als
Problem und bleibt ungelöst. Ein gespeicherter Bestwert kennt den Kontext
nicht, in dem er entstand.

**Der Code ist absichtlich unverändert.** Die naheliegende Reparatur — bei
Überschreitung einmal nachmessen und den besseren Wert nehmen — führt `work()`
zweimal aus, und mindestens ein Aufruf hängt an einem Zwischenspeicher
(`evaluate_cached`). Ein zweiter Durchgang wäre dort schneller, weil er den
Cache trifft, und aus einem roten Test würde ein **falsch grüner**. Das ist
schlimmer als der Zustand jetzt. Zwei Wege ohne dieses Risiko: den
Regressionsvergleich aussetzen, sobald andere Testdateien im Lauf sind (die
absoluten Schranken bleiben und prüfen weiter), oder den Bestwert je
Aufrufkontext getrennt halten. Beides ändert das Verhalten des Tors und gehört
angesagt, nicht nebenbei gemacht.

Gemessen auf einer Kugel mit 328 000 Dreiecken (§31 nennt seine Ziele für
200 000), Werte in `tests/.performance.json`:

| Messung | §31 | vorher | jetzt |
|---|---|---|---|
| Schichtanalyse, 0,2 mm | 300 ms | 2,35 s | **1,05 s** |
| Wandstärkenkarte | 3 s, im Hintergrund | 8,18 s, im Vordergrund | **3,08 s, im Hintergrund** |
| Orientierungssuche, 200 Lagen | 20 s | 32,2 s | **16,5 s** |
| Feature-Erkennung | 1 s | 0,44 s | 0,44 s |
| Auswertung aus dem Cache | 1 s | 0,3 ms | 0,3 ms |

Vier Änderungen. Drei nach dem Muster **nicht rechnen, was niemand liest**, eine
nach **das Vorhandene benutzen**:

* Die Wandkarte hat ihr Raster Schicht für Schicht geschnitten und dabei alle
  328 000 Dreiecke dreihundertmal durchlaufen. Jetzt ein Durchgang über alle
  Höhen — von 8,2 s auf 3,1 s, und damit im Ziel.
* Die Orientierungssuche liest aus jeder Schicht genau eine Zahl. Sie fragt
  jetzt `detail="support"` an, und die Strukturbreiten entfallen: 32 s → 16,5 s,
  ebenfalls im Ziel.
* Die Suche nach der kleinsten Strukturbreite hört auf, sobald eine Schicht
  dicker ist als alles, wovor §22.2 warnt. Ob eine Wand vier oder neun
  Millimeter hat, fragt kein Bericht — die Suche danach kostete mehr als der
  Rest der Schichtanalyse zusammen.

* **GEOS gibt die GIL frei.** Das Messen der Schichten läuft jetzt auf so vielen
  Threads, wie die Maschine hat: 1,73 s → 1,05 s. Gemessen, nicht vermutet —
  0,81 s auf einem Thread gegen 0,15 s auf acht.

Dieselbe Idee auf den Polygonaufbau angewandt war **langsamer** (0,758 s gegen
0,714 s): einzelne Polygone zu bauen hält die GIL, anders als die vektorisierten
Prädikate beim Messen. Die Änderung ist wieder draußen, die Messung steht als
Kommentar an der Stelle — damit sie niemand nochmal versucht.

Offen bleibt die Schichtanalyse selbst: 1,05 s statt 300 ms, also rund 650 ms
für die Größe, die §31 nennt. Was übrig ist, ist der Polygonaufbau in GEOS; das
zu schließen braucht einen kompilierten Kern, keine weitere Python-Idee.

### Der kompilierte Kern, nachgerechnet (14.08.2026)

Der Satz darüber stand zwei Phasen lang als Vermutung. Er stimmt — aber erst
die Gegenprobe zeigt, *warum*, und sie hat unterwegs zwei andere Annahmen
umgeworfen. Alle Zahlen auf einer Maschine, die rund dreimal langsamer ist als
die, auf der die Tabelle oben entstand; verglichen wird deshalb nur
untereinander.

**Was die Zeit wirklich kostet.** Warm gemessen liegt der Polygonaufbau bei
1078 ms gegen 455 ms für das Sammeln der Segmente — GEOS ist also tatsächlich
die größere Hälfte. Threads helfen dort nicht, sie schaden: Faktor 0,75 auf
vier Kernen, weil `polygonize` den Interpreter-Lock hält.

**Die billigere Erklärung, geprüft und verworfen.** `polygonize` löst ein
schwereres Problem als wir haben: Es nodet beliebig kreuzende Linien, während
unsere Segmente aus Dreiecken mit exakt geteilten Ecken kommen und paarweise
zusammenpassen. Die Ringe selbst zu verketten ist damit ein Durchlauf in O(n)
ohne eine einzige Fließkommaentscheidung. In Python gemessen: **1215 ms** —
also nicht schneller als GEOS, das mehr tut. Vektorisiert über alle Schichten
(Halbkanten, Zyklenzerlegung, Zeigerverdopplung) waren es **540 ms**, wieder
dieselbe Größenordnung. Drei Wege, ein Ergebnis: Python ist hier an der Decke,
und zwar nicht am Verfahren, sondern am Interpreter.

**Übersetzt sind es 11 ms** — Faktor 54 auf dieselben Zeilen. Daraus ist
`app/core/slice/_chain.pyx` geworden, gebaut mit `tools/build_slice_core.py`.
Gemessen am selben Körper, beide Wege im selben Prozess:

| Vorgang | über GEOS | übersetzt | Faktor |
|---|---|---|---|
| `slice_body`, 328 000 Dreiecke, 0,2 mm | 2732 ms | 2041 ms | **1,34** |
| Orientierungssuche, 200 Lagen | 48,2 s | 35,8 s | **1,35** |
| Wandstärkenkarte | 5074 ms | 4602 ms | 1,10 |

**Das Modul ist optional, und das ist keine Bequemlichkeit.** Fehlt es, nimmt
`_rings_from` den Weg über GEOS — gemessen 2732 ms gegen 2789 ms vor der
ganzen Änderung, also unverändert. Ein Klon ohne Compiler wird dadurch nicht
langsamer als vorher, er wird nur nicht schneller.

**Robuster, aber ausdrücklich nicht genauer — und das war ein Fehlschlag
unterwegs.** Der GEOS-Weg rundet die Enden auf sechs Nachkommastellen, damit
sie zusammenfinden; genau dort meldete ein Behälter mit drei Fächern einmal
9 463 mm² Überhang, den es nicht gab. Die Verkettung *braucht* das nicht: Sie
kennt die Kante, auf der ein Punkt liegt, und die ist für beide
Nachbardreiecke dieselbe ganze Zahl.

Der erste Anlauf hat daraus den Schluss gezogen, dann eben nicht zu runden.
Das kostete `test_evaluation.py`: `compensate_elephant_foot` zieht den
Querschnitt mit `buffer` ein, extrudiert die Differenz und schneidet sie ab —
und eine Boolesche Operation macht aus einer Abweichung in der **neunten**
Stelle eine andere Topologie. Am ausgehöhlten Quader kamen 17 erkannte
Merkmale heraus statt 14, darunter ein Stift, den es nicht gibt, und die
Mehrdeutigkeit, an der die Auswertung anhalten sollte, verschwand.

Also rundet die Verkettung genauso. **Der übersetzte Weg ist der schnellere,
nicht der genauere**, und was die Kante bringt, ist die Ringschließung, die
nicht mehr davon abhängt, dass die Rundung zwei Enden zusammenführt.

Bemerkenswert ist, wie knapp das durchgerutscht wäre: `tests/test_slice_core.py`
gab es schon und es war grün — es verglich Flächen und Löcher auf `rel=1e-6`.
Es vergleicht jetzt die **Punkte** und die Flächen auf `1e-12`; übrig bleibt
eine Abweichung von einer letzten Stelle, weil GEOS sich den Anfangspunkt
eines geschlossenen Rings selbst sucht und die Flächenformel dadurch in
anderer Reihenfolge summiert.

**Was jetzt die größte Position ist**, ist nicht mehr der Polygonaufbau,
sondern `_plane_segments` mit 893 ms — das Sammeln der Schnittsegmente in
numpy. Wer §31 weiter schließen will, misst dort weiter, nicht bei GEOS.

### Drei fremde Bibliotheken, geprüft (14.08.2026)

Anlass war die Frage, ob C- oder C++-Bibliotheken auf Dauer mehr Spielraum
geben. Die Lizenzen waren nie das Problem — die Freigabeliste lässt MIT, Boost
und MPL zu —, die Auslieferung schon:

* **CoACD** (MIT, `abi3`-Wheels für alle drei Plattformen) sollte V-HACD in
  `convex_parts` ablösen. **Verworfen, gemessen.** Auto Split nimmt von der
  Zerlegung eine einzige Zahl, die Stelle der Einschnürung, und dort trifft
  V-HACD näher (Abweichung 7,2 gegen 9,2 an der Hantel). Dazu ist CoACD in der
  genauen Einstellung zwei- bis fünfzigmal langsamer — 32,3 s gegen 0,66 s an
  `plate_holes.stl` —, und grob eingestellt liefert es nur noch ein Stück,
  also gar keinen Hinweis. Es gibt keine Einstellung, in der es gleichzeitig
  schnell und aussagekräftig ist. Damit ist das „prüfen" in Bauplan §36
  beantwortet.
* **pyclipr** (Clipper2, Boost) hat **kein Linux-Wheel**. Es einzubauen hieße,
  eine C++-Bauumgebung in die CI zu holen — genau das, was eine fremde
  Bibliothek ersparen sollte.
* **libigl** (MPL-2.0) liefert nur bis cp312 und **nicht für Windows**. Das
  Projekt verlangt Python ≥ 3.13 und zielt auf Windows; es ist damit heute
  nicht installierbar, unabhängig davon, ob es fachlich passte.

Das Muster taugt als Regel: Bei einer nativen Abhängigkeit entscheidet nicht
die Lizenz und nicht der Funktionsumfang, sondern ob es Räder für Windows,
macOS und Linux in der Python-Version dieses Projekts gibt. Alles andere ist
eine Bauumgebung, die jemand pflegen muss.

### Die Schwelle selbst ist ein offener Punkt (nachgetragen 22.08.2026)

Alles oben stand als Prosa da, und niemand führte es. Ein roter Leistungstest
heißt nach diesem Abschnitt **nicht** „nicht fertig" — das ist die teuerste
Auskunft der Datei, und sie lag 163 Zeilen tief ohne Kästchen.

- [x] **Die Regressionsschwelle schlug an, ohne dass etwas langsamer wurde.**
      Zwei von fünf Läufen rot, je an einem anderen Test, immer an der
      25-%-Schwelle und nie an einem absoluten Zielwert — die Aufrufreihenfolge
      allein macht achtunddreißig Prozent (`sketch_solve_200`: 114 ms allein,
      162 ms hinter `test_slice.py`). Der Code ist absichtlich unverändert:
      Nachmessen bei Überschreitung führt `work()` zweimal aus, und mindestens
      ein Aufruf hängt an `evaluate_cached` — aus einem roten Test würde ein
      falsch grüner, und das ist schlimmer. Wartet auf die Entscheidung zwischen
      den zwei Wegen ohne dieses Risiko: den Regressionsvergleich aussetzen,
      sobald andere Testdateien im Lauf sind (die absoluten Schranken bleiben und
      prüfen weiter), oder den Bestwert je Aufrufkontext getrennt halten. Beides
      ändert das Verhalten des Tors, gehört also angesagt und nicht nebenbei
      gemacht.

      **Am 22.08.2026 zweimal gemessen, und das ist der Beleg, den der Abschnitt
      oben nicht hatte** — dieselbe Software, dieselbe Maschine, derselbe Tag,
      zwei Läufe von zwei Sitzungen:

      | | Fremdlast | Ergebnis |
      |---|---|---|
      | Lauf A | 48 % CPU (zwei `test_ui.py`-Läufe davor, ein Spurlauf daneben) | **5 failed**, 14 passed |
      | Lauf B | 16 % CPU, sonst nichts | **19 passed**, Exit 0 |

      Alle fünf in Lauf A waren die Schwelle, kein absoluter Zielwert:
      `ingest_dense` 1,27× (3917 ms gegen Bestwert 3082), `detect_medium` 1,25×
      (942 gegen 752), `sketch_solve_200` 1,33×, dazu Orientierungssuche,
      Subdivision und Blending. In Lauf B liegt die Orientierungssuche bei
      17,5 s, Subdivision bei 2,5 s, Blending bei 1,3 s — alle unter ihrer
      Schranke.

      Der Abschnitt oben stützte sich auf zwei von fünf Läufen **einer**
      Sitzung. Jetzt steht daneben: Ein roter Leistungslauf sagt zuerst etwas
      über die Maschine und erst danach über den Code. Wer eine Regression
      meldet, misst vorher ein zweites Mal auf einer ruhigen Maschine.

      **Entschieden am 22.08.2026 (Bauplan §31): Bestwert je Aufrufkontext.**
      Der andere Weg — den Vergleich aussetzen, sobald andere Testdateien im
      Lauf sind — schaltet ihn fast immer ab: Das Tor läuft geteilt, ein Prozess
      je Fensterdatei und alles übrige in einem Zug, also sind „andere
      Testdateien im Lauf" der Normalfall. Ein Vergleich, der dann aussetzt,
      prüft nichts mehr. §31 hält außerdem fest, dass ein roter Leistungstest
      allein nicht „nicht fertig" heißt — als einziger roter Test in diesem
      Projekt. Damit steht es an der Stelle, an der jemand danach sucht, und
      nicht 163 Zeilen tief in einer Arbeitsliste.

      **Gebaut in `3190971`, und zwar so, wie §31 es entschieden hat.**
      `tests/test_performance.py` führt die Marken je Aufrufkontext:
      `_invocation_key()` bildet ihn aus der **Menge** der Testdateien im
      Prozess (`alone` oder `with N more (<hash>)`), `_read_marks()` hält je
      Kontext `{"best", "strikes"}` und liest zwei ältere Formate mit, und
      `measure()` vergleicht gegen den Bestwert *dieses* Kontexts. Die
      kontextlosen Altmarken stehen unter `UNKNOWN_CONTEXT` und werden nicht
      mehr verglichen. Dazu kam etwas, das der Punkt nicht einmal forderte:
      `REGRESSION_STRIKES = 2` — ein Ausschlag ist Last, zwei in Folge sind eine
      Richtung, also die Handregel aus §31 als Code. Der Fall, der den Punkt
      aufmachte (`sketch_solve_200`: 114 ms allein, 162 ms hinter
      `test_slice.py`), fällt damit nicht mehr in denselben Vergleich. Gebaut
      von 3d-druck-33.

## P11 — Gehosteter Backend
- [–] **Bewusst nicht gebaut.** §27 knüpft diese Phase an nachweisbare
  Nachfrage; die gibt es nicht. Ein Dienst ohne Nutzer wäre Arbeit auf Vorrat,
  dazu ein Server, eine Abrechnung und eine Datenschutzzusage, die alle
  gepflegt werden müssten.

Was stattdessen sichergestellt ist: Die Schnittstelle steht schon so, dass ein
gehosteter Dienst sie ohne Änderung erfüllen könnte. `MeshBackend` kennt genau
`text_to_mesh` und `image_to_mesh` (§27) — kein Nutzercode, keine Dateipfade,
kein Zustand. Dass eine zweite Umsetzung daneben passt, ist keine Behauptung:
`ScriptedMeshBackend` ist genau das und trägt die ganze Weg-3-Abnahme.

Der Auslöser für diese Phase wäre: Nutzer, die erzeugen wollen und keine
Grafikkarte dafür haben, und die das auch sagen. Dann nach §27 — Text oder Bild
rein, Mesh raus, Eingaben nach Auslieferung löschen, Serverstandort EU.

## P12 — B-Rep-Kern
- [x] Zweiter Kern, `kind` im Objekt, Übergang B-Rep → Mesh
- [x] Fasen und Verrundungen, STEP rundreisefähig

Anmerkungen zu P12:

* **Ein `Solid` erfüllt dasselbe `Mesh`-Protokoll wie alles andere.** Ansicht,
  Prüfbericht, Schichtanalyse und Export arbeiten damit unverändert weiter.
  Wo der Kern es exakt weiß, antwortet er aber exakt: Volumen und Fläche kommen
  aus OpenCASCADE, nicht aus den Dreiecken — bei einer Verrundung ist der
  Unterschied nicht akademisch.
* **`kind` folgt dem Körper, nicht der Behauptung.** Die Auswertung setzt es
  nach jeder Operation aus dem tatsächlichen Objekt. Eine Netz-Operation auf
  einem exakten Körper bekommt die Vernetzung und liefert ein Netz zurück —
  und der Objektbaum sagt das dann auch.
* **Der Rückweg besteht nicht, aber ein Undo schon.** Die Umwandlung ist eine
  Operation im Stack; sie zurückzunehmen holt den exakten Körper zurück, weil
  neu gerechnet und nicht geflickt wird.
* **Merkmale kommen aus der Topologie**, nicht aus Clustern und Zylinderfits
  (§30). Eine Zylinderfläche wird nur dann als Bohrung gemeldet, wenn sie eine
  volle Umdrehung beschreibt — eine Verrundung ist auch ein Zylinder.
* **Kein Rückfallketten-Ersatz.** Die Kette aus §17.2 gibt es, weil Netze sich
  darüber uneinig sind, was innen ist. Zwei B-Rep-Körper sind das nicht; hier
  ist ein Fehlschlag ein echter Fehler und kein Anlass für einen gröberen
  Versuch.
* OpenCASCADE ist optional (`pip install -e ".[brep]"`). Ohne den Kern sagen
  die betroffenen Operationen das in einem Satz, alles andere bleibt unberührt.

## P13 — Skizzen und tiefere Konstruktion

Beschlossen am 31.07.2026, Bauplan v10 (§30.1, §40): **die Veröffentlichung
wartet auf diese Phase** — der Launch führt die Skizzen als Kernargument. Das
Ziel dahinter: so wenig Fremdprogramme wie möglich; das fremde CAD vor dem
Import ist der größte verbliebene Grund, Solidon zu verlassen. Der Slicer
bleibt bewusst außen (§22.5), OpenSCAD blieb Rückfallebene — bis es am
26.08.2026 ganz entfiel, weil die Skizzen dieser Phase es überflüssig gemacht
hatten. Die
Veröffentlichungsreste aus P8 (Remote/CI, Zertifikat, Vertrieb, Betatest)
laufen parallel und stehen weiter oben unter „Bewusst offen".

- [x] Lizenzprüfung der Solver-Wege — kürzer als gedacht: scipy ist seit dem
      `geom`-Extra deklariert und steht mit BSD-3 in der Freigabeliste; der
      eigene Solver braucht **keine neue Abhängigkeit**. CadQuery/build123d
      damit gegenstandslos; SolveSpace und py-slvs waren GPL und nie im Rennen
- [x] `core/sketch`: Datenmodell als Verträge in `core/types.py` (§9) —
      alle Freiheitsgrade sind Punktkoordinaten, `targets` sind Punktindizes
      über die flache Punktliste; ohne Qt
- [x] 2D-Solver (`core/sketch/solver.py`): deterministisch, ohne Zufall;
      unterbestimmt zählt Freiheitsgrade im Ergebnis, überbestimmt und
      widersprüchlich werfen `SketchConflictError` mit benanntem Paar —
      Duplikate findet die Ranganalyse, Widersprüche der Restfehler
- [x] Maße als Ausdrücke der Parametergrammatik (§13) — `@width` und
      `=@width/2 + 5` laufen durch denselben Auswerter wie überall, kein
      `eval`; alles außerhalb der Grammatik wird abgelehnt
- [x] Grundformen (`core/sketch/shapes.py`): Rechteck, Langloch, Kreis,
      Vieleck als Skizzen mit Bedingungen, nie als rohe Punktlisten — und der
      eigene Solver hat das eigene Langloch abgelehnt: der erste
      Bedingungssatz war in der symmetrischen Lage linear abhängig. Die
      Disziplin gilt auch für die eigenen Formen
- [x] Sechs Skizzen-Ops gegen den B-Rep-Kern (`sketch_extrude`,
      `sketch_pocket` mit Flächen-Klick und durchgehend, `sketch_revolve`,
      `sketch_sweep`, `sketch_loft`) — der Umriss reist als exakte Kurve
      (`core/sketch/profile.py`, `core/brep/profiles.py`); jede Op steht
      gegen eine geschlossene Formel: der Torus trifft Pappus, der Kreis Pi
- [x] Formgebungs-Ops: exakte Schale (oben offen), Formschräge und der
      exakte Gewindebolzen als echter helikaler Sweep — erst kürzen, dann
      vereinigen, sonst scheitert die Boolesche Stufe; Fase und Verrundung
      ziehen in die neue Kategorie Formgebung um
- [x] Die gezeichnete Skizze reist als Parameterwert (`kind="sketch"`,
      JSON-Text in `core/sketch/serialize.py`) und ersetzt in
      `sketch_extrude`, `sketch_pocket`, `sketch_revolve` und `sketch_sweep`
      die Grundform — §15 gilt unverändert: kein verstecktes Attribut,
      Bearbeiten ist `change_params`. Der Text wird gelesen wie jede fremde
      Eingabe (auch `true` und `NaN` sind keine Koordinaten), und der
      Cache-Schlüssel der Auswertung kennt die Projektparameter, die ein
      Maßausdruck im Text liest — sonst überlebte der alte Körper die
      Parameteränderung im Cache. Der Agent bekommt den Parameter nicht
      (§26: Grundformen statt roher Punktlisten) — das Tool-Schema bietet
      ihn nicht an, und die Sitzung lehnt ihn auch geraten ab
- [x] Grafischer Skizzeneditor (Zeichnen, Bedingungen über Werkzeugleiste
      und Kontextmenü), offscreen testbar — `app/ui/sketch_editor.py`,
      angebunden über das `kind="sketch"`-Feld jedes Operationsdialogs;
      die Ebene kommt weiter aus dem Flächenparameter der Op. Die offene
      Frage von damals ist beantwortet, wie der Punkt es nahelegte: kein
      Befund an der Op — die Freiheitsgrade stehen live in der Statuszeile
      des Editors, und das Feld fasst sie zusammen
- [x] Agenten-Suite von 30 auf 33 Fälle: Sechseck-Sockel, Deckel mit Tasche,
      Handlauf-Bogen — und der Trichter dreht sich um: was den
      OpenSCAD-Rückfall brauchte, kann `sketch_loft` jetzt im Haus. Die
      Quote gegen ein echtes Modell misst weiter `tools/run_agent_suite.py`
      (kostet Geld, läuft auf Zuruf)
- [x] Ende-zu-Ende: Gehäuse mit passendem Deckel von leerer Szene bis 3MF
      (`tests/test_sketch_end_to_end.py`) — und der Weg fand zwei stille
      Fehler: `create_lid` fraß im Stapel das Gehäuse (die Op-Tests riefen
      die Funktion immer direkt auf), und die Hüllquader von OpenCASCADE
      schlagen die gespeicherte Vernetzung mitsamt Durchhang auf — die
      Schale fand auf einem gehashten Körper keine Oberseite mehr
- [x] Leistungsziel §31: 200 Bedingungen unter 100 ms — **90 ms** Ende zu
      Ende, gemessen in `test_performance.py`. Zwei Entscheidungen tragen
      den Wert: jede Bedingung bringt ihre **analytische Ableitung** mit
      (numerische Differenzen kosten eine Auswertung je Variable), und der
      Trust-Region-Schritt läuft über `lsmr` statt einer dichten SVD je
      Iteration (700 ms → 90 ms, nachgemessen). Nebeneffekt: die exakte
      Jacobimatrix macht die Ranganalyse verlässlich, an der die Erkennung
      überbestimmter Skizzen hängt

## P13.1 — Der Skizzeneditor zieht in den Viewport

Robert am 24.08.2026: „schau dir das 2d zeichnen an, ich finde es sehr
umständlich und wofür ist es genau? am viewport ändert sich nichts, bei
draufsicht, seitenansicht usw sieht man auch keinen unterschied.“

Drei Beobachtungen, und **eine** Zeile erklärte alle drei:
`switch(self.middle_stack, panel)` tauschte die Ansicht gegen die
Zeichenfläche aus. Am Viewport änderte sich nichts, weil er nicht mehr da
war; die Ansichtswechsel wirkten auf ein verdecktes Widget; und wozu das
Zeichnen gut ist, konnte man nicht sehen, weil das Modell fehlte, auf dem
gezeichnet wird.

Konzept, Entscheidungen und Pakete stehen in
`konzepte/konzept-skizze-im-raum-2026-08.md`. Hier nur, was gebaut wurde:

- [x] Weltpunkt ↔ Zeichenpunkt als reine Funktionen (`to_world`, `to_plane`,
      `ray_hit` in `app/core/sketch/planes.py`) — OCC-frei und damit
      offscreen prüfbar. Der Grund ist Entscheidung G: Unter
      `QT_QPA_PLATFORM=offscreen` existiert kein Plotter, also muss alles
      Prüfbare **vor** VTK gerechnet werden
- [x] Die gelöste Skizze als Punktfolgen im Raum (`profile.curves_of`),
      abgetastet nach Sehnentoleranz
- [x] Die Kamera schwenkt auf jede Ebene (`view_on_plane`), auch auf eine
      angeklickte Fläche. `camera_for_plane` nimmt dafür `image_normal`
      (x × y) und **nicht** `frame.normal`: Die XZ-Ebene ist linkshändig,
      und über die Normale stand die Kamera hinter ihr — die Vorderansicht
      hätte die Skizze spiegelverkehrt gezeigt
- [x] Skizze und Raster liegen als Netz in der Szene, das Modell tritt
      durchscheinend zurück. Das Raster hängt **nicht** an der gelösten
      Skizze — sonst fehlt es bei leerer Zeichnung, also genau dann, wenn
      man es braucht
- [x] Ein Klick trifft die Ebene rechnerisch (`_sketch_hit` → `ray_hit`)
      statt über einen Picker. Ein `vtkCellPicker` trifft nur Geometrie, und
      über einer Durchgangsbohrung gäbe es nicht einmal ein Dreieck dahinter
- [x] Eine Fläche anklicken beginnt dort eine Skizze — Kontextmenüeintrag
      „Auf dieser Fläche zeichnen“, nur bei `kind == "face"`
- [x] Die Bedingungen stehen als **Reiter** neben Prüfbericht und Chat, nicht
      als Klappabschnitt darunter
- [x] Die Rasterweite kommt aus der Kamera (`Viewport.pixels_per_mm`), nicht
      aus der unsichtbaren Zeichenfläche. Deren Maßstab steht auf dem
      Startwert, weil dort niemand mehr zoomt: gezeichnet wurden 20 mm,
      gefangen auf 1 mm
- [x] Die Kameradistanz hat eine Untergrenze (`LEAST_PLANE_DISTANCE`). Ohne
      sie übernahm der Skizzenmodus in einer leeren Szene pyvistas
      Startstellung von 1,62 Einheiten — 918 Bildpunkte je Millimeter, ein
      Raster von 0,1 mm. Getroffen hätte es ausgerechnet **Weg 2**
- [x] Die Zeichenebene wird orthografisch gesehen und die Projektion beim
      Verlassen auf den Wert des Nutzers zurückgestellt. Gefunden hat das
      kein Test, sondern das Bild: Die Korpusplatte stand trapezförmig da,
      mit sichtbaren Seitenwänden, unter der Zeile „Draufsicht (XY)“
- [x] Abbau: `set_zone_margins`, `in_viewport()` und `_in_viewport` sind weg.
      `SketchField` und `SketchEditorDialog` bleiben — sie sind der zweite
      Weg über den Operationsdialog

- [x] **Die Warnung „die Skizze ragt darüber hinaus" fehlt im Viewport-Modus
      — geschlossen am 28.08.2026.**
      Der Bauraumrand steht wieder im Bild — Kanten und Maßskala bleiben beim
      Zeichnen sichtbar, nur der Boden tritt ab. Der **Warnsatz** dazu liegt
      aber in der Zeichenfläche (`sketch_editor.py:1954`), und die ist
      unsichtbar. Das Handbuch verspricht ihn: „wer darüber hinauszeichnet,
      liest es an derselben Linie“. Damit ist das Versprechen halb
      eingelöst — man sieht die Grenze, aber nicht den Satz, der sie benennt.
      Die vorhandene Statuszeile ist diese Stelle jetzt: Sobald ein gelöster
      Punkt außerhalb liegt, nennt sie den Bauraum und die Handlung „Punkte
      innerhalb des Rahmens verschieben“. Der gestrichelte, verstärkte Rand
      bleibt die zweite Kodierung im Bild. Ändert sich der Bauraum erst nach
      dem Öffnen, zieht die Statusmeldung ebenfalls sofort nach.

**Was dabei nebenbei auffiel und behoben ist:** Die Ziffern 1–3 für die Ebene
lagen an `WidgetWithChildrenShortcut` und hätten nach dem Schnitt nie mehr
gefeuert. Die Bedienleiste verdeckte die untere Bildhälfte. Und fünf Tests in
`test_viewport_decisions.py` bauten einen Viewport ohne `qt_app` in der
Signatur — in der vollen Datei rettet sie ein früherer Test, einzeln gefahren
stirbt der Lauf mit 0xC0000409.

## P14 — Die Oberfläche einlösen

Durchsicht der gesamten Bedienung: 29 Dateien unter `app/ui/`, das Register mit
seinen 70 Operationen, die Einstellungen und die Verdrahtung zur Sitzung.
Achtundzwanzig Funde, und keiner davon eine Geschmacksfrage — jeder ist
entweder ein Versprechen, das der Code nicht einlöst, oder eine Stelle im
Bauplan, die noch keinen Nutzer hat.

Sie haben fünf Ursachen. Wer die fünf behebt, behebt die achtundzwanzig; wer
die achtundzwanzig einzeln behebt, baut sie in einem halben Jahr wieder ein.

### Woran es liegt

**1 — Das Dokument kennt nur Operationen.** Alles, was keine Op ist, steht
außerhalb von Transaktion und Undo: Parameter, Passungen, Druckeinstellungen,
Drucker und Material. `History.apply` lehnt eine Transaktion ohne Operationen
sogar ausdrücklich ab. Die Folgen sind die schwersten Funde der Durchsicht:

* Ein Wert in der Parameterleiste wird direkt ins Dokument geschrieben
  (`main_window.py:1397`). Kein Undo — Strg+Z nimmt stattdessen die letzte
  *Operation* zurück. Kein `_dirty` — der Titel zeigt kein `*`, und weil
  `closeEvent` nur `if self.session.modified` sichert, ist die Änderung beim
  Schließen weg.
* `agent/apply.py` hat für genau dieses Problem eine Lösung — der Vorschlag
  trägt `previous_parameters` und `previous_fits` mit, und `apply.undo()`
  spielt sie zurück. **Nur ruft die Oberfläche `apply.undo()` nie auf.** Sie
  ruft `history.undo()`, und das kennt nur Operationen. Ein Strg+Z nach einem
  angenommenen Vorschlag nimmt dessen Operationen zurück und lässt seine
  Parameter und Passungen stehen. Das ist ein Verstoß gegen Regel 16, und die
  Tests decken ihn zu, weil sie `apply.undo()` direkt aufrufen statt über den
  Weg, den ein Mensch nimmt.
* Der Drucker eines Projekts wird in `new_project` gesetzt und danach nie
  wieder (`project.py:129`). Es gibt keinen Weg, ihn zu ändern — wer ein
  Beispielprojekt oder eine fremde Datei öffnet, arbeitet dauerhaft gegen
  einen fremden Bauraum. Bett, Anordnen, Kollisionsprüfung und Auto Split
  hängen alle daran.

**2 — Die Oberfläche kennt den Zustand nicht, den sie zeigt.** In
`main_window.py` steht kein einziges `setEnabled`. Alle 70 Operationen sehen
bei leerer Szene benutzbar aus; wer eine anklickt, bekommt eine modale
Sackgasse („Bitte zuerst ein Objekt auswählen"). `undo_action` und
`redo_action` werden in Attribute gelegt und nie wieder angefasst. Dieselbe
Blindheit an drei weiteren Stellen: `show_error` gibt die gewählte Handlung
zurück und **keiner der neun Aufrufer wertet sie aus** — wer auf *Reparieren
und erneut versuchen* klickt, schließt einen Dialog; der Menühinweis zu
*Beenden* verspricht eine Rückfrage, die `closeEvent` nie stellt; und
`recovery_candidates()` für namenlose Projekte hat keinen Aufrufer, die
Sicherung nach einem Absturz vor dem ersten Speichern wird also nie angeboten.

**3 — Die Oberfläche rechnet selbst.** Die Analysekarte liegt vorbildlich in
einem Thread. Vier andere Rechnungen nicht: der Schnittschieber sendet
`valueChanged` fortlaufend und löst pro Pixel einen booleschen `cut()` je
Körper im Qt-Hauptthread aus; `_slice_of` schneidet synchron und hängt damit
an Strg+P und an der G-Code-Gegenprobe; der Bausteinkatalog rendert beim
Öffnen alle Vorschauen nacheinander ohne Wartezeiger; ein Agentenzug dauert
zehn bis sechzig Sekunden und hat keinen Abbrechen-Knopf. Dazu die Wurzel:
**die Anzeige-Dezimierung aus §18.9 gibt es nicht.** §31 nennt 500 000
Dreiecke als Schwelle; der Viewport zeichnet immer das volle Netz.

**4 — Einstellungen haben keinen Ort.** Es gibt keinen Einstellungsdialog.
Thema und Navigation liegen unter *Ansicht*, Sprache, Drucker und Material
unter *Hilfe → Erste Schritte*. Wer den Drucker unter „Hilfe" sucht, hat
geraten. Drei deklarierte Einstellungen sind deshalb tot: `display_unit` wird
nirgends gelesen (§19.3 Zoll gibt es nicht), `diff_palette` wird gespeichert,
aber beim Start nie an den Viewport gegeben (die Alternative für
Farbfehlsichtige ist unerreichbar), und `check_for_updates` lässt sich nur
durch Handbearbeitung von `settings.json` einschalten. Die Sprache wirkt erst
nach einem Neustart, und niemand sagt das.

**5 — Gestufte Tiefe ist gedacht, nicht gebaut.** `collapsible()` in
`panels.py` heißt so, baut aber nur eine Überschrift ohne Umschalter — die
drei Abschnitte links klappen nicht ein, obwohl §2.5 das verlangt. „Weitere
Einstellungen" ist eine `QGroupBox(checkable=True, checked=False)`, und die
graut ihre Kinder aus, statt sie wegzuklappen. In den Druckeinstellungen ist
deshalb das größte Element des Dialogs — das Register mit 48 Feldern —
standardmäßig graue tote Fläche mit `stretch=1`. Das Häkchen liest sich
außerdem wie ein Schalter, der etwas bewirkt.

### Entscheidungen vor dem Code

**E1 — Die Transaktion trägt auch, was keine Operation ist.** `Transaction`
bekommt ein Feld `changes: DocumentChange | None` mit je einer Vorher- und
einer Nachher-Seite für Parameter, Passungen, Druckeinstellungen, Drucker und
Material. `History.apply` nimmt sie entgegen und darf dann ohne Operationen
auskommen; `undo` und `redo` spielen sie mit zurück und vor. Das ist keine
Bauplanänderung: §15.5 nennt die Transaktion „die Einheit, auf die sich
Verlauf, Differenzansicht und Chatverlauf beziehen" und beschränkt sie
nirgends auf Operationen. Es ist eine Formatänderung — also `format_version`
hoch, Migration, alte Beispieldatei einchecken, nach der Checkliste in
`AGENTS.md`. `Proposal.previous_parameters` und `apply.undo()` entfallen
danach: der Agent baut eine `DocumentChange` wie jeder andere Aufrufer, und es
gibt genau einen Weg zurück statt zwei.

**E2 — Löschen ist eine Operation, die nichts erzeugt.** `delete_object` mit
`consumes=1, produces=0`. Nachgesehen statt vermutet: die Auswertungsschleife
trägt das bereits — `evaluate.py:206` entfernt jedes Eingangsobjekt, das nicht
wieder herauskommt, und die Ausgabeschleife läuft dann null Mal. `History`
vergibt für `produces=0` eine leere Ausgabeliste, und eine spätere Operation
auf dem gelöschten Körper wird beim Anlegen abgelehnt, weil er nicht mehr in
`_known_objects()` steht. Kein neuer Mechanismus, keine Ausnahme von Regel 3 —
die Op ändert kein Objekt, sie gibt keines zurück.

**E3 — Sichtbarkeit und Isolieren sind Ansicht, nicht Dokument.** §18.8
verlangt beides im Objektbaum. Sie kommen trotzdem *nicht* in den Stapel: was
ausgeblendet ist, ändert nichts an dem, was gerechnet, exportiert und gedruckt
wird, und ein Verlauf, in dem jeder Lidschlag steht, ist als Verlauf nichts
mehr wert. Das Fenster führt eine Menge ausgeblendeter Kennungen, der Viewport
liest sie neben `entry.visible`, der Baum zeigt sie mit Symbol **und** Wort
(Regel 18). Das bestehende Feld `ObjectEntry.visible` bleibt, was es ist: die
Vorgabe aus der Auswertung, die eine Op eines Tages setzen darf.

**E4 — Der Drucker wird über E1 gewechselt, nicht über eine Op.** Er ist
Projektkontext wie die Druckeinstellungen (§12 `"scene": {"printer", "material"}`),
kein Schritt im Stapel. Als `DocumentChange` ist er rücknehmbar, steht im
Verlauf und löst eine Neuauswertung aus — Toleranzen sind Verweise (§12), also
ändert sich Geometrie, und das muss im Verlauf stehen.

**E5 — Die Menüleiste bekommt eine zweite Ebene, das Register nicht.** Heute
sind es siebzehn Menüs: vier von Hand und dreizehn aus den Kategorien.
`category` bleibt, wie der Bauplan sie in §25 festlegt; die Oberfläche legt
eine Zuordnungstabelle Kategorie → Menügruppe darüber und macht aus den
dreizehn fünf mit Untermenüs (*Objekt*, *Erzeugen*, *Ändern*, *Bausteine*,
*Druckvorbereitung*). Neun Menüs insgesamt. Eine Tabelle in der Oberfläche ist
chirurgisch; die Kategorien umzusortieren wäre eine Bauplanänderung für ein
Anzeigeproblem.

**E6 — Fehlerhandlungen laufen über einen Vermittler.** `show_error` bekommt
eine Zuordnung `dict[str, Callable]`. Das Hauptfenster stellt die allgemeinen
(`report_error`, `open_settings`, `show_locations`, `scale_to_fit`,
`split_model`, `use_voxel_stage`), der Aufrufer ergänzt das, was nur er kann
(`retry`). Eine Handlung ohne Handler wird nicht angeboten — lieber ein Knopf
weniger als einer, der nichts tut. Ein Test über alle `Action`-Konstanten
hält das fest.

**E7 — Die Anzeige-Dezimierung ist die Antwort auf drei Wartezeit-Funde.**
Erst sie, dann die Threads: ein Schnittschieber auf einem für die Anzeige
dezimierten Netz ist bereits erträglich, und ein Thread um eine Rechnung, die
zehnmal zu groß ist, verschiebt das Problem nur. §18.9, Schwelle aus §31.

### Etappen

Sieben Einheiten, jede für sich committierbar, jede mit grüner Suite am Ende.
Die Reihenfolge ist keine Vorliebe: Etappe 1 trägt 2 und 5, und die
Dezimierung aus 7 macht die Arbeit in 4 billiger, ist aber keine Voraussetzung
dafür.

#### Etappe 1 — Was keine Operation ist, wird trotzdem zurückgenommen

Fundament (E1). Ohne sie sind vier weitere Funde nicht sauber zu beheben.

- [x] `DocumentState` und `DocumentChange` in `core/types.py`, beide Seiten;
      `change_for()` baut sie aus dem heutigen Stand, damit kein Aufrufer die
      Vorher-Seite selbst zusammensucht
- [x] `Transaction.changes`, `History.apply(..., changes=)`, leere Draft-Liste
      erlaubt, sobald Änderungen dabei sind
- [x] `History.undo`/`redo` spielen Änderungen mit — eine Funktion `restore()`
      für beide Richtungen
- [x] Format 4 → 5, Migration `_add_transaction_changes`, `example_v5.p3d`
      eingecheckt (sie zeigt eine Transaktion, die nur aus einer Änderung
      besteht)
- [x] `agent/apply.accept` baut eine `DocumentChange`; `apply.undo` und
      `Proposal.previous_parameters`/`previous_fits` entfallen
- [x] Parameterleiste: Änderung als Transaktion mit Titel „Parameter *name*",
      `_dirty` folgt daraus; die Rückfrage aus §15.4 gilt hier wie im Menü
- [x] ~~`set_print_settings` wird eine Transaktion~~ — **zurückgenommen beim
      Bauen.** Der Punkt stand aus Symmetrie im Plan, nicht aus einem Befund:
      `set_print_settings` setzt `_dirty` längst korrekt, es war nie etwas
      kaputt. Und die Einstellungen ändern nichts an dem, was die Auswertung
      rechnet — sie reisen zum Slicer. Damit gilt hier dieselbe Grenze wie bei
      der Sichtbarkeit in E3: in den Verlauf kommt, was die Auswertung
      beeinflusst. Drucker und Material tun das (Bauraum, Toleranzverweise),
      die Druckeinstellungen nicht.

*Abnahme erfüllt:* Strg+Z nach einer Parameteränderung stellt den alten Wert
her; ein Undo eines *neu angelegten* Parameters entfernt ihn, statt eine Null
zu hinterlassen; Strg+Z nach einem angenommenen Agentenvorschlag stellt
Parameter **und** Passungen wieder her — geprüft über `History.undo`, also
über den Weg, den auch das Fenster nimmt. `example_v1` bis `v5` öffnen und
rechnen. Suite: 2106 grün, rot bleibt allein die bekannte Orientierungssuche.

#### Etappe 2 — Der Objektbaum, wie §18.8 ihn beschreibt

- [x] `delete_object` nach der Op-Checkliste (E2), Kürzel `Entf`, Test
- [x] Sichtbarkeit je Objekt (E3) — Symbol und Wort, im Baum und im Kontextmenü
- [x] Isolieren (§18.8): alles außer der Auswahl ausblenden, ein zweiter Aufruf
      hebt es auf
- [x] Herkunft im Baum: aus welcher Operation und Transaktion ein Körper kommt
- [x] Mehrfachauswahl (`ExtendedSelection`), in **Klickreihenfolge** geführt —
      „A minus B" ist nicht „B minus A", und die Reihenfolge im Baum weiß
      davon nichts
- [x] `OperationDialog` gibt Namen aus und Kennungen weiter, kein freies
      Textfeld mehr

**Drei Funde beim Bauen, keiner davon aus der Durchsicht:**

**Die drei Booleschen mit zwei Eingängen waren über das Menü nicht
ausführbar.** `inputs_for` gab immer genau ein Objekt zurück, `union_objects`
und die beiden anderen erwarten zwei — der Stapel lehnte mit „erwartet eine
andere Anzahl an Objekten" ab. Aufgefallen ist es erst, als die
Mehrfachauswahl die Frage stellte, welches denn das zweite sei.

**Der Stapel hielt tote Objekte für lebendig.** `_known_objects()` sammelte
jede je vergebene Nummer statt der Körper, die am Ende übrig sind. Für das
Entfernen fiel es auf; es galt aber längst für jede Vereinigung: eine
Operation auf einem verbrauchten Körper wurde angenommen und scheiterte erst
beim Rechnen. Jetzt rechnet der Stapel dieselbe Bilanz wie die Auswertung.
Nebenbei ist damit die Behauptung in E2 berichtigt — sie stimmte aus dem
falschen Grund.

**Die Quellenauswahl war mit Körpern gefüllt.** `kind="source"` und
`kind="object"` teilten sich eine Liste, und Objekte standen darin. Wer
*Modell laden* im Verlauf wieder öffnete, bekam Körper angeboten, wo eine
Datei gemeint war. Beide haben jetzt ihre eigene Liste, und ein gespeicherter
Wert, den keine davon kennt, wird angezeigt statt ersetzt.

*Abnahme erfüllt:* Importieren, entfernen, Strg+Z — der Körper ist wieder da.
Zwei Körper anklicken und abziehen, ohne etwas zu tippen. Ausblenden,
Isolieren und Herkunft in `tests/test_ui.py`; ein Test hält fest, dass eine
parameterlose Operation ohne Dialog läuft (Regel 19).

#### Etappe 3 — Die Oberfläche liest ihren eigenen Zustand

- [x] Menüeinträge aktivieren und deaktivieren nach Auswahl und Szenenstand;
      Undo und Redo folgen `history.can_undo`/`can_redo`. Damit entfallen die
      drei modalen Sackgassen. **Die Werkzeugzeile bleibt anklickbar** — sie
      schaltet Ansichten, und ihre Leisten melden inline, was fehlt
      („Wählen Sie zuerst ein Objekt", in der Leiste statt in einem Fenster).
      Ein ausgegrauter Schnittknopf bei leerer Szene wäre Strenge ohne Nutzen
- [x] Fehlerhandlungen verdrahten (E6): sieben Handler im Fenster, und
      `handlers_of()` findet sie vom Dialog aus über das Elternfenster — damit
      zeigen auch Druckeinstellungen und Variantendialog wirksame Knöpfe, ohne
      sie durchzureichen
- [x] Beim Beenden, bei *Neu* und beim Öffnen nach ungesicherten Änderungen
      fragen — drei Knöpfe (Speichern, Verwerfen, Abbrechen), kein „Wirklich?".
      Wer im Dateidialog abbricht, hat nicht gespeichert, und dann wird auch
      nichts verworfen
- [x] Menühinweis zu *Beenden* stimmt danach wieder
- [x] Wiederherstellung für namenlose Projekte — über `find_recovery(None)`,
      nicht über `recovery_candidates()`: `autosave_path(None)` ist ein fester
      Pfad, es kann also nur eine geben. Die zweite, schlechtere Antwort auf
      dieselbe Frage ist entfernt. `Session.recover()` lässt den Pfad leer,
      damit ein „Speichern" nicht die Sicherung überschreibt, und
      `save_project` räumt sie auf

**Was beim Bauen dazukam:** `offered_actions()` ist eine eigene Funktion
geworden, weil sie sich sonst nicht prüfen ließe — ein Test, der dafür den
Dialog aufmacht, hängt am modalen Fenster. Genau das ist beim Schreiben
passiert, und es steht seit der letzten Durchsicht im Kopf von
`tests/test_ui.py`.

Drei Handlungen sind bewusst nicht verdrahtet und werden deshalb auch nicht
angeboten: `use_voxel_stage` (die Rückfallstufe ist kein Parameter, den ein
Dialog setzen kann), `choose` (dafür fragt der Kern über `ctx.ask`, bevor er
wirft) und `choose_printer` — das kommt mit Etappe 5. Ein Test hält fest, dass
jede `Action`-Konstante entweder einen Handler hat oder in dieser Liste steht.

*Abnahme erfüllt:* Bei leerer Szene ist keine Operation anklickbar, die einen
Körper braucht; „Vereinigen" wird erst mit dem zweiten gewählten Körper aktiv;
jeder gezeigte Knopf im Fehlerdialog führt etwas aus; Schließen mit
ungesicherter Änderung fragt. Suite: 2122 grün.

#### Etappe 4 — Nichts rechnet mehr im Hauptthread

- [x] Schnitt- und Explosionsschieber entprellt (120 ms). Der Schnitt bleibt
      im Hauptthread: die Entprellung macht aus dreißig Rechnungen je Zug eine,
      und das reicht. Ein Arbeiter dafür wäre ein zweiter Weg, auf dem
      Geometrie in die Ansicht kommt — die Dezimierung aus Etappe 7 löst den
      Rest an der Wurzel
- [x] `_slice_of` asynchron, mit Meldung in der Statusleiste. Der Druckdialog
      erzwingt sie nicht mehr, sondern nimmt sie, wenn sie vorliegt — genau
      das, was sein Docstring seit jeher behauptet hat
- [x] Bausteinvorschauen nacheinander im Leerlauf, eine je Durchlauf der
      Ereignisschleife; die Liste ist sofort lesbar
- [x] Abbrechen für den Agentenzug — mit **eigenem** Abbruchsignal, denn
      Auswertung und Agent laufen unabhängig, und ein abgebrochener Vorschlag
      darf keine laufende Berechnung mitreißen. Der Balken läuft ohne Ende:
      wie viele Schritte ein Zug braucht, steht vorher nicht fest, und eine
      geratene Prozentzahl wird geglaubt
- [x] `wait_for_idle` schließt Eingaben aus (`ExcludeUserInputEvents`) statt
      alle Ereignisse zu verarbeiten. Die Signale der Arbeiter müssen
      durchkommen, ein Menüklick mitten im Warten nicht

*Abnahme erfüllt:* Kein Weg mehr über 2 s ohne Fortschritt und Abbrechen. Zwei
Tests mussten nachziehen, weil sie das synchrone Verhalten festhielten — beide
warten jetzt auf das, worauf auch ein Mensch wartet.

#### Etappe 5 — Einstellungen an einem Ort

- [x] Dialog *Bearbeiten → Einstellungen* (Strg+Komma), getrennt in zwei
      Gruppen: was die Anwendung betrifft und was für **neue** Projekte gilt.
      Der Unterschied stand vorher nirgends und ist der Grund, warum Drucker
      und Material unter „Hilfe" gelandet waren
- [x] `display_unit` bekommt Leser: Statusleiste, Objektbaum und die Maße der
      Auswahl. Dazu `format_volume()` im Kern — in Zoll sind Kubikzentimeter
      keine Antwort, und der Unterschied ist zu groß, um ihn zu übergehen
- [x] `diff_palette` und alles andere Gespeicherte beim Start anwenden;
      `_apply_settings()` ist die eine Stelle dafür, vorher waren es zwei und
      zwei Werte kamen in keiner davon vor
- [x] Der Sprachwechsel sagt, dass er auf den nächsten Start wartet — der
      Katalog wird beim Start installiert, und Texte, die schon auf dem
      Bildschirm stehen, wechseln nicht mit
- [x] Drucker und Material des offenen Projekts wechselbar (E4) — im
      Druckeinstellungs-Dialog, wo sie vorher als Beschriftung standen. Als
      Transaktion, also rücknehmbar, und die Vorgaben des Dialogs lösen sich
      sofort neu auf
- [x] *Erste Schritte* verweist auf den Dialog

*Abnahme erfüllt:* Auf Zoll umgeschaltet zeigt die Statusleiste 0,7874 für
einen 20-mm-Würfel, und das Netz bleibt bei 20; ein Projekt lässt sich auf
einen anderen Drucker umstellen, das Profil folgt, und ein Undo nimmt es
zurück. Suite: 2129 grün.

#### Etappe 6 — Entdeckbarkeit

- [x] Menügruppen (E5) — neun Menüs statt siebzehn: *Objekt*, *Erzeugen*,
      *Ändern*, *Bausteine*, *Vorbereiten*. Eine Gruppe aus einer Kategorie
      steht flach, sonst bekommt jede Kategorie ihr Untermenü. Eine Kategorie,
      die diese Tabelle nicht kennt, bekommt weiter ihr eigenes Menü — sie
      soll auftauchen, nicht verschwinden
- [x] Befehlspalette nimmt Datei-, Ansichts- und Werkzeugbefehle auf;
      `ToolStrip.tool_titles()` und `strip_title()` haben ihren Aufrufer
- [x] `Escape` schließt das offene Werkzeug
- [x] *Ansicht → Alles einpassen* auf `Home`; dazu bekommt der erste Körper
      einer leeren Szene die Kamera von selbst
- [x] Tastaturnavigation im Viewport nach §19.2: Zoom auf den Standardkürzeln,
      Durchblättern der Körper auf Strg+Tab und Strg+Umschalt+Tab, reihum
- [x] Symbole für die vier Knöpfe der oberen Werkzeugleiste

**Zwei Funde beim Bauen:**

**Die Menügruppen wären nie übersetzt worden.** Der Abgleich der Sprachdateien
liest literale `tr("…")`-Aufrufe; ein `tr(variable)` sieht er nicht. Die Titel
sind jetzt mit `_()` markiert — dieselbe Falle wartet auf jeden, der Texte in
einer Tabelle sammelt (Regel 20).

**Menüs brauchen einen Besitzer auf der Python-Seite.** PySide gibt für ein
Menü bei jedem Zugriff einen neuen Wrapper, und wird einer eingesammelt, nimmt
er das C++-Objekt mit. Solange nur die Leiste die Menüs kannte, ging das gut;
mit der zweiten Ebene wurde daraus ein Absturz. Das Fenster hält seine Menüs
jetzt selbst.

*Abnahme erfüllt:* Neun Menüs in der Leiste, jede Operation weiter erreichbar
(der Test sucht rekursiv), jeder Fenster-Befehl in der Palette.

#### Etappe 7 — Gestufte Tiefe und Anzeigeleistung

- [x] `collapsible()` klappt wirklich ein — ein Knopf mit dem Titel darauf,
      damit die ganze Zeile die Fläche ist, die man trifft, und der gedrückte
      Zustand die zweite Kodierung (Regel 18)
- [x] „Weitere Einstellungen" klappt weg statt auszugrauen — in `op_dialog.py`.
      **Im Druckeinstellungs-Dialog war der Fund nur halb richtig:** das
      Register verschwand längst, sein Rahmen behielt aber den Dehnungsfaktor
      und damit den ganzen freien Raum. Ein leerer Kasten statt grauer Felder;
      jetzt bekommt er zugeklappt auch keinen Platz mehr
- [x] Anzeige-Dezimierung ab 500 000 Dreiecken auf 200 000 (§18.9, §31). Sie
      erreicht weder Kern noch Export. Ein Körper mit einer Analysekarte wird
      **nicht** dezimiert: die Karte trägt einen Wert je Dreieck des Originals
- [x] Nachkommastellen aus dem erklärten Wertebereich: was ganz unter einem
      Millimeter liegt, bekommt drei. Eine Toleranz von 0,075 wurde beim
      Öffnen sonst zu 0,08 — eine stille Änderung an einer gemessenen Zahl
- [x] Chat mehrzeilig; Eingabe sendet, Umschalt und Eingabe macht den Absatz.
      Die Vorschlagszeile nennt bis zu drei Operationen beim Namen und zählt
      erst darüber

*Abnahme erfüllt:* Kein Dialog zeigt graue Felder oder leere Rahmen, die
niemand ausgeschaltet hat. Suite: 2136 grün.

### Was nicht dazugehört

* **Live-Vorschau im Operationsdialog.** Wäre die größte Einzelverbesserung
  gegenüber Fusion und Blender und ist deshalb kein Nebenher — eigene Phase,
  nach P14. Der bestehende Weg (anwenden, ansehen, Doppelklick im Verlauf,
  korrigieren) trägt bis dahin. *Eingelöst — siehe „Die zwei bekannten
  Lücken" unten.*
* **Linke Maustaste dreht als Vorgabe.** Bambu Studio, OrcaSlicer und
  PrusaSlicer tun das; §2.9 gibt Cura vor. Die Vorgabe zu wechseln wäre eine
  Bauplanänderung und bleibt eine Entscheidung für sich — **als viertes
  Wahlschema ist es gebaut** (`orbit`), und dabei fiel auf, dass der
  Menühinweis der Vorgabe seit jeher das Gegenteil dessen beschrieb, was sie
  tut: „links drehen, rechts schieben" ist Bambu, nicht Cura.

### Die Aufräumrunde

Drei Kleinigkeiten, die in der Durchsicht als „echt, aber klein" standen:

- [x] **Verlauf zeigt, was ein Redo zurückholt.** Zurückgenommene
      Transaktionen verschwanden spurlos; ob es noch etwas
      wiederherzustellen gab, verriet allein der Zustand des Menüeintrags.
      Sie stehen jetzt unten, durchgestrichen und ausgegraut — wie ein
      verworfener Chatbeitrag und aus demselben Grund (§26.3)
- [x] **Filterzeile im Prüfbericht**, Text und Schweregrad unabhängig
      voneinander. Die Zählung darüber bleibt die des ganzen Berichts: ein
      Filter, der auch die Zusammenfassung filtert, verschweigt, dass es noch
      etwas anderes gibt
- [x] **Einträge aus „Zuletzt geöffnet" entfernen** — über das Kontextmenü.
      Die Datei bleibt, wo sie ist

## Aus der Analyse für Neulinge und Kunden

Anlass war die Frage, wie die Anwendung auf Neulinge und zahlende Kunden
wirkt. Der Befund: die Onboarding-Substanz trägt — Startbildschirm mit
Beispielen, Handbuch-Knopf, überspringbarer Erststart, Fehler als Vorschlag.
Die verbliebenen Lücken lagen fast alle **vor dem ersten Start und neben der
App**: beim Kaufweg, beim Vertrauen und beim Erwartungsmanagement der KI.
Behoben in dieser Runde:

* **Es gab keinen Weg, Kunde zu werden.** Kein Preis, kein Kontakt — der
  einzige angebotene Weg („Adresse im Impressum") führte auf einen
  Platzhalter. Jetzt: **eine Support-Adresse** als Konstante
  in `app/branding.py`, gelesen von Über-Dialog, Fehlerbericht-Dialog,
  README, Impressum und beiden Startseiten. Der Fehlerbericht sagt jetzt
  auch, wohin der abgelegte Ordner kann — er verschickt weiter nichts.
* **Kaufmodell auf der Website** (damalige Entscheidung, später ersetzt):
  Ursprünglich standen hier 14 Tage kostenlos testen und **49 € zur
  Einführung, später 79 €**, alle 1.x-Updates inklusive. Aktueller Stand vom
  28.08.2026: vollständige Demo bis einschließlich 30.10., Verkauf ab 01.11.
  zunächst **ohne zusätzliche Testphase**, **69 € bis 31.01.2027 und danach
  99 €**. Der gepflegte Testpfad bleibt mit `TRIAL_FROM = None` deaktiviert.
  Einordnung: Plasticity als nächster
  Vergleich (Indie-CAD, Einmalkauf) liegt bei 149 $, Shapr3D bei ~299 €/Jahr,
  Fusion weit darüber, die Hobby-Konkurrenz bei null. Eine 1.0 einer neuen
  Marke ohne Nutzerbasis startet darunter; „wir verbessern uns weiter" ist
  als 1.x-Zusage eingelöst, und der Einführungspreis belohnt die, die früh
  einsteigen.
* **Das Kernversprechen war beim Auspacken leer.** Der Erste-Schritte-Dialog
  bekam den Chat-Zugang (Zustandszeile + Knopf zum Schlüsseldialog), den
  sein Docstring seit jeher versprach; das Fenster weckt den Chat danach
  ohne Neustart. Der einzige Weg dorthin war vorher ein Knopf in einem
  Panel, das ein neuer Nutzer noch nie gesehen hat.
* **Der Satz aus §27 fällt jetzt bei der Einrichtung.** Wacht der Chat über
  Ollama auf, fragt ein Arbeiter die installierten Modelle ab
  (`llm.ollama_size_warning`): unter 7 Milliarden Parametern oder gar nicht
  installiert gibt es einen Satz im Chat-Panel — einmal, bei der
  Einrichtung, nicht bei jedem Start. Ein Server, der nicht antwortet,
  bleibt Schweigen statt Warnung.
* **Ein Anwendungssymbol existiert.** Gestaltete SVG-Quelle
  (`app/images/icon/solidon3d.svg`: isometrischer Körper, Bohrung,
  Schichtlinien, Markenfarbe), gerastert von `tools/make_icon.py` zu
  `packaging/solidon3d.ico` (DIB + 256er-PNG, ohne neue Abhängigkeit) und
  `website/icon.svg`; das Fenster rastert die Quelle zur Laufzeit
  (`icons.application_icon`). Eingebunden in Spec, Installer-Skript und
  alle Website-Köpfe. Damit ist die Vorbedingung für AppImage/Flatpak da.
* **Die Website sagt jetzt, was die KI kostet und braucht.** Weg 3 nennt
  ComfyUI und Grafikkarte, die Systemvoraussetzungen nennen die 14B/10-GB-
  Wahrheit für den lokalen Chat und die laufenden API-Kosten beim eigenen
  Schlüssel — Kunden verzeihen Kosten, die vorher dastanden. Dazu das erste
  Bildschirmfoto auf der Startseite; eines, das fertig danebenlag.

**Damals weiterhin offen, weil es niemand von dort aus erledigen konnte:**
Postfach, Anschrift, Zertifikat gegen SmartScreen, CI, Zahlungsanbieter,
Lizenzschlüssel-Mechanik und ein Betatest mit fremden Nutzern. Heute stehen
Postfach, Anschrift, Lizenzschlüssel, Geräteaktivierung und beide Offline-Wege;
offen bleiben insbesondere Signierung/Notarisierung, Merchant of Record,
fachliche Rechtsprüfung und Feldläufe. Die Tests sagen, dass der Code tut, was
gemeint war, nicht, dass ein Fremder ihn bedienen kann. Damals war außerdem die Web-Domain
solidon3d.rsdigital.de, die Mail-Domain rs-digital.org — zwei Schreibweisen
nebeneinander, bewusst so entschieden oder zu vereinheitlichen.
*Aufgelöst am 06.08.2026: die erste Domain existierte nicht. Alles läuft
jetzt über `solidon3d.rs-digital.org`, siehe „Website".* — *Und am 08.08.2026
endgültig: eigene Domain `solidon3d.de`, Support `support@solidon3d.de`. Aus
zwei Domains ist wieder eine geworden, diesmal die des Produkts.*

### Zwei Befunde, die nie in einer Liste standen (nachgeprüft 22.08.2026)

Beide stehen in `konzepte/konzept-erstnutzer-2026-08.md` (3.1 und 5.9) und
standen dort von Anfang an in keiner Zeile der Statustabelle — das Dokument sagt
das über sich selbst. Von zwölf solchen Punkten waren beim Nachprüfen am
22.08.2026 sieben längst behoben und einer entschieden; diese zwei sind es
nicht.

- [x] **Erzeugen und Ändern sind reine Verteilermenüs — gemessen und
      umgesetzt am 23.08.2026 (`a6d59fc`, `bfff72b`), und die Entscheidung vom
      22.08. hielt nur zur Hälfte.**

          Objekt        scene                              5 Zeilen  ->  flach
          Erzeugen      primitive 5, import 3,
                        sketch 5, label 2                 18        ->  bleibt tief
          Ändern        sieben Kategorien                 40        ->  bleibt tief
          Bausteine     parts                             20        ->  eigene Ebene
          Vorbereiten   prepare 6, colour 3               10        ->  flach möglich

      Die Entscheidung sagte, *Erzeugen* werde flach und der Quader koste zwei
      Klicks statt drei. Mit 18 Zeilen gegen die Zwölfergrenze wird er das
      nicht. **Der Fehler darin ist genau der, den sie beheben wollte:** Sie
      stützte sich auf „Grundformen hat vier Zeilen" — die Zahl **einer**
      Kategorie — und hat damit Kategorien gezählt, wo sie Zeilen zählen wollte.

      Was blieb, ist kleiner und echt und ist gebaut: *Vorbereiten* steht
      flach — zehn Zeilen, keine Untermenüs. Neun Operationen sparen einen
      Klick, darunter Ausrichten fürs Drucken und Teilen.

      **Den Ausschlag gab nicht der Klick, sondern dass zwei Maße dieselbe
      Sache maßen** (3d-druck-b8): Der Aufbau entschied nach Kategorienzahl,
      die Grenze misst in Zeilen. Eine Gruppe bekam eine Zwischenebene, weil
      sie zwei Kategorien hat — nicht, weil sie zu lang ist. `group_is_flat`
      beantwortet die Frage jetzt an **einer** Stelle statt an dreien.

      Zwei Aussagen stecken darin, und die zweite ging beim ersten Anlauf
      unter: Eine Gruppe mit einer einzigen besetzten Kategorie ist immer
      flach, gleich wie lang sie ist — ihre Zwischenebene hieße genauso wie
      das Menü darüber („Bausteine → Bausteine → Deckel erzeugen"). Gefunden
      an b8s Wächter, nachdem sie beim Ersetzen verlorengegangen war.

      Ursprünglich stand hier: `registry.py:79` legt
      vier Kategorien unter *Erzeugen* und sieben unter *Ändern*, jede als
      eigenes Untermenü. Wer einen Quader will, klickt dreimal, und
      „Grundformen" hat vier Zeilen, wo die Grenze bei zwölf liegt. Wartet auf
      eine Entscheidung, wie tief ein Menü sein darf: flach ziehen sprengt die
      Neun-Menü-Grenze aus `tests/test_interface_limits.py`, ist also ein Tausch
      und keine Verbesserung. Die Namensdopplung „Vorbereiten →
      Druckvorbereitung" aus demselben Befund ist weg — `prepare` heißt heute
      „Teilen und Anpassen".
- [x] **Zwei fehlgeschlagene Operationen stapeln zwei modale Fehlerfenster —
      behoben am 23.08.2026 (`2904d28`, 3d-druck-b8).** Von den drei
      Möglichkeiten des Punkts („unterdrücken, anhängen oder zählen") ist es
      **anhängen mit Zähler im Kopf** geworden: Der zweite Fehler geht in das
      offene Fenster, statt ein zweites zu stellen. Das Bildschirmfoto bleibt
      vom ersten — es zeigt den Zustand, in dem es schiefging.

      Ursprünglich:
      `report_error` ruft in `app/ui/main_window.py:6376` unbedingt
      `dialog.exec()`; es gibt keine Sperre und kein Sammeln. Der Text darin ist
      vorbildlich („Das war ein Programmfehler, nicht Ihre Schuld"), zweimal
      wegklicken ist einmal zu viel. Wartet auf eine Entscheidung, was der
      zweite Fehler tun soll — unterdrücken, an den offenen Bericht anhängen
      oder zählen.

## P15 — Konstruieren und zeigen

Der Vergleich mit SindriCAD, Meshy und dem, was 3Druck als Stand der Software
meldet: zweiundzwanzig Lücken, davon vier abgelehnt. Solidon lag bei
Druckintelligenz und Dokumentlogik deutlich vorn und bei Konstruktions-
werkzeugen, Bediensprache und Darstellung deutlich zurück. Das Konzept steht in
`konzepte/konzept-p15-konstruieren-und-zeigen.md` und ist vollständig abgearbeitet.

**Die Grenzen kamen zuerst, nicht zuletzt.** Sieben prüfbare Obergrenzen in
`tests/test_interface_limits.py` — höchstens neun Menüs, zwölf Zeilen je Menü,
acht Umschalter, acht Felder auf der Vorderseite eines Dialogs, genau ein
Menüeintrag je Operation. Sie wurden **vor** dem Wachstum eingezogen; installiert
man sie danach, sind sie kein Riegel mehr, sondern eine Bestandsaufnahme. Der
erste Lauf fand sofort ein Menü mit 23 Zeilen und eine Kategorie ohne Symbol.

**Was dazukam.** Umgebungsverdeckung und Körperkanten in der Ansicht; die
Druckplatte mit gefülltem Grund, Maßstab und Kontaktschatten; der Skizzenmodus
ohne Dialog, mit Bauraumgrenze, Referenzmaß, Splines, Skizzenmustern und der
angeklickten Fläche als Ebene; Texturen als echte Geometrie, flach und
umlaufend; Gitterfüllungen; Muster, Press/Pull und Thicken; zwei
Kürzelbelegungen und eine erzeugte Kürzelübersicht; mehrere Generierungs-
versuche; und die MCP-Schnittstelle, mit der ein zweites Programm dieselben
Operationen aufruft wie die Menüs.

**Vier Dinge wurden begründet nicht gebaut** und stehen mit ihrem Grund im
Konzept: Text als Skizzenkontur (die Zeichensatz-Abhängigkeit macht aus einer
Projektdatei eine, die auf einem anderen Rechner anders aussieht),
`offset_face` (dieselbe Operation wie `push_face` unter zweitem Namen),
assoziative Skizzenmuster (sie verlangten einen zweiten Abhängigkeitsgraphen
neben dem Op-Stack) und vier parallele Generierungsläufe (hier läuft ComfyUI auf
derselben Grafikkarte, an der jemand sitzt).

### Was die Arbeit gelehrt hat

**Messen schlägt begründen.** Der Radius der Umgebungsverdeckung stand zuerst
auf acht Millimetern, mit einer plausibel klingenden Begründung — die Messreihe
zeigte ihn als schwächsten Wert der ganzen Reihe. Genommen sind zwei, und auch
das nicht der rechnerisch beste Wert: bei einem Millimeter streifen ebene
Flächen sichtbar, was die Zahl allein nicht sagt. Man muss hinsehen.

**Ein Bild prüft, was ein Review nicht sieht.** Der doppelte ViewCube fiel erst
im neu aufgenommenen Handbuchbild auf. Der Kontaktschatten brauchte sechs
Anläufe, und die drei ersten sahen im Code richtig aus.

**Ein negatives Volumen erklärt eine Voxelstufe.** Die Zylinder-Umlaufung der
Texturen spiegelte: die Determinante der Abbildung war negativ, das gebogene
Feld hatte −420 mm³, und die Boolesche Vereinigung floh auf Stufe 4 — 45
Sekunden statt 0,4, der Körper zwei Zehntel zu groß. Wer eine langsame Boolesche
Operation sieht, misst zuerst das Volumen ihrer Eingänge.

**Der eigene Test findet den eigenen Irrtum.** Die Zahl der Operationen war um
sechzehn falsch, weil ohne geladenes Register gemessen; die erste Version der
Grenzprüfung zählte Registerkategorien statt Menüs und hätte damit die Lösung
für das Problem gehalten.

## Gegen das Wettbewerbsfeld gehalten (11.08.2026)

`konzepte/konzept-wettbewerb-2026-08.md` zieht auf, was `konzepte/konzept-sindricad.md` an einem
einzelnen Konkurrenten gemessen hat: sechs Gruppen — parametrisches CAD,
Direktmodellierer, Einsteigerwerkzeuge am Modellkatalog, Mesh-Reparatur,
Slicer, KI —, jeder Bereich der Anwendung dagegen gehalten.

**Der Befund ist nicht, dass etwas fehlt, sondern dass das Falsche vorn
stand.** Führend sind wir beim Anpassen fremder Modelle (Meshmixer
eingestellt, 3D Builder abgekündigt), bei der Druckbarkeit vor dem Slicen und
bei `auto:<material>`. Die Website führte mit Säule A — dem einen Bereich, in
dem Autodesk gerade Foundation-Modelle für editierbares B-Rep auffährt.

### Umgesetzt

- [x] **GLB hinausschreiben** (B4 aus dem SindriCAD-Konzept). Mit Namen und
      Farben: glTF kennt Farben nur an Ecken, deshalb je Materialslot ein
      eigenes Teilnetz — sonst kommt die Grenze zwischen roter Platte und
      blauer Schrift als Verlauf über das halbe Teil an. Die Kommandozeile
      nimmt ihre Formatliste jetzt aus dem Schreiber.
- [x] **Mehrsprachigkeit als Gerüst.** `available_languages()` liest das
      Katalogverzeichnis; Erstlauf, Einstellungen, Einsammler, Handbuch und
      Abbildungen lesen es. Eine neue Sprache ist eine Datei. Der
      Übersetzungstest prüft jede gefundene, nicht mehr nur die englische —
      halb übersetzt einchecken geht damit nicht. Das Dezimaltrennzeichen
      kennt jetzt auch Spanisch, Französisch, Italienisch und Portugiesisch.
- [x] **Modell aus dem Netz** (§16.3). Verweis aus dem Browser ablegen oder
      *Datei → Modell aus dem Netz*, Feld mit der Zwischenablage vorbelegt.
      Beides geht durch `Session.import_payload`, also durch dieselbe
      Operation wie eine Datei von der Platte. Nur http/https, Größengrenze
      beim Lesen statt am `Content-Length`, Herkunft in `Source.origin`. Eine
      Adresse mit HTML dahinter ist eine Modellseite und bekommt genau diesen
      Satz — ausgewertet wird nichts.
- [x] **Texturmuster sichtbar** (B2). Bild und Name je Zeile in der Auswahl,
      gezeichnet aus `pattern_shapes`. Dazu eine Handbuchabbildung mit allen
      achten und ein Abschnitt auf der Startseite.
- [x] **Website.** Weg 1 als Aufmacher, Windows und Linux ausdrücklich mit
      macOS als benannter Lücke (eigene FAQ-Frage), GLB bei den Formaten.

      **Die FAQ-Frage war falsch, und zwar zu unseren Lasten** (am 14.08.2026
      gegen die CI geprüft). Sie sagte „Nein, vorerst nicht … für Windows und
      Linux", während `build.yml` seit je vier Pakete baut: `windows-latest`,
      `ubuntu-latest`, `macos-13` (Intel) und `macos-latest` (Apple Silicon),
      jeweils mit Bundle-Prüfung, `codesign`-Schritt und `ditto`-Archiv. Drei
      andere Stellen derselben Seite — Auszeichnung für Suchmaschinen,
      Zusicherungsliste und Systemvoraussetzungen — nannten den Mac korrekt.
      Eine Seite, die Kunden von einer Plattform abrät, die sie ausliefert,
      kostet mehr als eine Lücke. Beide Sprachen nachgezogen; was tatsächlich
      fehlt, ist allein die Apple-Signatur, und die Systemvoraussetzungen
      sagten das schon vorher richtig.

### Was der Durchgang durch das laufende Fenster gefunden hat

Zwei Zeilen unter der Musterauswahl, die gerade Bilder bekommen hatte, standen
die Werte weiter englisch: „Art: raised", „Auflegen: flat". Über das ganze
Register waren es **sechsundzwanzig** Auswahlwerte. Behoben, und
`tests/test_translations.py` lässt nur noch durch, was sein eigener Name ist
(M4, 6x3, mm, x, DejaVu Sans, gyroid).

Der zweite Fund war ein eigener Fehlbefund: die beworbenen **77 Operationen**
sind richtig. Ein Zähllauf über `walk_packages` kam auf 61, weil die sechzehn
`insert_*`-Operationen der Bausteine erst mit `load_operations()` entstehen.
`tests/test_website.py` prüft die Zahl gegen das Register und hat es gefangen,
bevor die falsche Zahl auf der Seite stand.

### Offen, mit Entscheidung dahinter

- [ ] **Sichtbarkeit.** Solidon ist fertiger als das, worüber geschrieben
      wird, und unbekannt. Keine Entwicklungsaufgabe.
- [ ] **macOS ausliefern.** Die Suite läuft dort bei Tags grün; es fehlen
      Apple-Signatur und die Bereitschaft, eine dritte Plattform zu stützen.
      Die Website sagt es jetzt ausdrücklich, statt es auszulassen.

      **Der Paketierschritt fehlt nicht mehr** (nachgesehen am 14.08.2026):
      `build.yml` baut das Bundle, prüft es auf seine ausführbare Datei,
      signiert mit einer Developer-ID sofern das Secret liegt, packt als zip,
      rechnet die Prüfsumme über `shasum -a 256` und lädt je Architektur ein
      eigenes Artefakt hoch — Intel und Apple Silicon getrennt. Was wirklich
      fehlt, ist enger und benennbar: das **Apple-Zertifikat** und die
      **Notarisierung**. Der gesperrte CI-Weg steht inzwischen: `notarytool`
      wartet auf Apple, `stapler` heftet und prüft das Ticket, `spctl` prüft den
      Installationsweg. Offen sind Apple-Konto, Developer-IDs, CI-Geheimnisse
      und der Feldlauf beider Architekturen; ohne sie hält Gatekeeper eine
      geladene Anwendung weiterhin an.
- [x] **G-Code an die Maschine senden** (B3) — **entschieden: nein**, am
      13.08.2026 (`konzepte/konzept-wettbewerb-2026-08.md`, Teil 7 Frage 2). §28 meint
      mit „Drucker" das Zurücklesen; Senden wäre eine Bauplanänderung, und die
      wird nicht gemacht: **Die Übergabe an den Slicer bleibt die Grenze, die
      Datei bleibt im Ordner.**

      Der Punkt stand danach noch sieben Tage als offen im Register — eine
      Entscheidung, die getroffen ist, gehört nicht in eine Arbeitsliste.
      Geschlossen am 20.08.2026.

      **Was das kostet, gehört dazu:** Der letzte Meter bleibt beim Wettbewerb.
      Bambu, Orca und Prusa schicken die Datei über das Netz an die Maschine,
      SindriCAD sogar an den Snapmaker U1; wir hören beim Ordner auf. Der
      Tausch ist bewusst — eine ganze Klasse von Netzwerkfehlern, die wir nicht
      stützen müssen — und er gehört ausgesprochen, wie „kein macOS-Zertifikat"
      und „keine Rückfallebene ohne Grafikkarte" auch. Grenzen stehen auf der
      Download-Seite, nicht in einer Fußnote.
- [x] **Weitere Sprachen befüllen.** Erledigt und am 14.08.2026 nachgezählt:
      `app/i18n/locales/` führt fünf Kataloge — `en`, `es`, `fr`, `it`, `pt` —
      mit je **2 426 Einträgen**, keiner leer. Was in einem Katalog wie die
      deutsche Quelle aussieht, sind Eigennamen und Maßangaben (24 bis 48 je
      Sprache: `mm`, `M4`, `6x3`, `DejaVu Sans`, `gyroid`), und die sollen so
      stehen. Die Zahl der Sprachen steht dabei nirgends im Code —
      `available_languages()` zählt das Verzeichnis.
- [x] **Skizze bedienerisch fertig** (B1). Die Ändern-Gruppe stand schon;
      die übrigen Punkte aus `konzepte/konzept-bedienung.md` Teil 4 sind seither
      nachgekommen — die Stand-Notiz dort führt alle neun als durch, im Code
      nachgeprüft am 13.08.

## Die Demo bis 30.10.2026 (12.08.2026)

Entschieden: eine öffentliche Demo statt eines Testlaufs. Start **20.08.2026**,
Ende **30.10.2026**, kostenlos, vollständig, ohne Schlüssel. Danach fällt am
10.10. die Entscheidung zwischen 1.0 und einer zweiten Runde. Das Konzept mit
allen Abwägungen steht in `konzepte/konzept-demo-2026-10.md`; hier steht, was
davon gebaut ist.

### Was der gründliche Durchgang gefunden hat

Der erste Durchgang las die Unterlagen, der zweite sah nach — gegen GitHub,
den Webserver und die Paketierung. Fünf Funde:

- [x] **Die Setup-Datei ließ sich nicht bauen.** PyInstaller baute nach
      `dist/Solidon`, `make_installer.py` suchte `dist/Solidon3D`. Die
      Umbenennung hatte die Paketierung nie erreicht; die CI trug den alten
      Namen an vier weiteren Stellen. Der Name kommt jetzt überall aus
      `app/branding.py`.
- [x] **Das Handbuch im Paket hatte keine Bilder.** `app/images/manual/` stand
      nicht in den `datas` — F1 hätte an jeder Abbildung eine Lücke gezeigt,
      stillschweigend. `tests/test_packaging.py` hält beides fest: kein
      zweiter Ort für den Namen, und jedes Verzeichnis mit Nicht-Python-
      Dateien muss ins Paket.
- [x] **Der Segmentierungsfehler auf dem Ubuntu-Runner.** Seit dem 06.08. starb
      jeder Lauf an derselben Zeile — `HistoryPanel.show_document`,
      `self.list.clear()`. Eine Messung mit zerlegter Suite zeigte, dass der
      Absturz *wandert*: er hing an keinem Test, sondern an den Fenstern, die
      sich über den Lauf ansammelten. Ein `window`-Fixture gibt sein Fenster
      zurück und überlässt es dem Speicherbereiniger; sammelt Python es ein,
      während eine Zustellung läuft, schreibt `clear()` in freigegebenen
      Speicher. Unter Windows behält der Allokator die Seite, unter Linux gibt
      er sie zurück. Die Fixture zerstört Fenster jetzt planmäßig
      (`deleteLater` plus `processEvents`), und `MainWindow.release()` schließt
      dabei den VTK-Interactor — ohne das stirbt der **nächste** Fensteraufbau.
- [x] **Das Repository ist öffentlich** und hieß bis heute `Formwerk`.
      Umbenannt auf `Solidon`; die Sichtbarkeit ist Roberts Entscheidung und
      steht auf öffentlich. Damit ist H5 (kompiliertes Prüfmodul) eine Bremse
      und keine Hürde — H1 hält weiter.

      **Am 14.08.2026 nachgeprüft und zwei Reste nachgezogen**, die die
      Umbenennung nicht erreicht hatte. Die API bestätigt beides —
      `full_name: RS-Digital-Studio/Solidon`, `private: false`, der alte Name
      antwortet mit 301. Aber der lokale `origin` zeigte weiter auf
      `.../Formwerk.git` (GitHub leitet weiter, deshalb fiel es nie auf), und
      der Kopf von `build.yml` begründete die Ein-Plattform-Matrix damit, das
      Repository sei privat und die Minuten gezählt. Öffentliche Repositories
      zahlen für die Standard-Runner nichts; die Begründung war weg, die
      Beschränkung stand noch. Beides steht jetzt richtig da — die Matrix
      selbst bleibt, aber mit dem Grund, den sie wirklich hat (Rückmeldezeit),
      und mit dem Hinweis, was sie kostet: Ein Fehler, der nur unter Windows
      auftritt, fällt sonst erst am Tag der Veröffentlichung auf.
- [ ] **DMARC fehlt** für `solidon3d.de`. SPF und MX stehen (netcup), der
      Eintrag `_dmarc` ist nicht gesetzt. Gehört ins CCP.

### Gebaut

- [x] **Stichtag im Kern.** `store.DEMO_UNTIL` ersetzt die Frist ab dem ersten
      Start; `Activation.deadline` und `.over` sagen der Oberfläche, woran sie
      ist. Der Testlaufmarker verliert damit seine Bedeutung. Zwei Tests halten
      dagegen: einer weckt, wenn der ausgelieferte Stichtag verstrichen ist,
      der andere verbietet einer 1.x-Version überhaupt einen Stichtag.
- [x] **Version 0.1.0** (am 14.08.2026 von 0.7.0 heruntergesetzt, entschieden
      von Robert). Die Null vorn ist Mechanik: `key.current_major()` liest sie,
      also greift ein 1.x-Kaufschlüssel in der Demo nicht — und der
      Update-Hinweis zeigt später auf die 1.0. Die 7 dahinter war nie
      begründet; die 1 ist der Anfang einer Zählung, die weitergeht.

      **Die Zählregel steht jetzt dabei:** letzte Stelle plus eins je
      ausgeliefertem Bau, vordere Stellen nur bei einer größeren Änderung.
      Sieben Stellen tragen die Zahl, zwei davon von Hand (`app/branding.py`,
      `pyproject.toml`) — und bis heute hielt die beiden nichts zusammen außer
      Aufmerksamkeit. `test_the_version_is_the_same_in_both_places_that_carry_it`
      tut es jetzt.
- [x] **Die Texte.** Statuszeile dauerhaft (nicht erst am vorletzten Tag),
      Über-Dialog, Freischaltdialog, Ersteinrichtung.
- [x] **Der Schluss.** Nach dem Stichtag startet weder Fenster noch
      Kommandozeile; die Meldung nennt das Datum, die Website und den Verbleib
      der eigenen Dateien.
- [x] **Zwei Menüeinträge**: nach einer neuen Version sehen (mit Antwort in
      allen drei Fällen) und Rückmeldung schreiben.
- [x] **Rechtstexte.** EULA §4a für die Demo; AGB und Widerruf sagen, dass sie
      ab dem Verkaufsstart gelten.
- [x] **Website.** Beide Startseiten führen die Demo, zwei neue Fragen
      beantworten das Ende.
- [x] **Startseite geteilt** (14.08.2026). Sie war auf **14 Bildschirme**
      gewachsen, und der Preis begann erst bei Bildschirm 11 — der
      Funktionsblock allein war mit 4809 px 36 % der Seite. Funktionen und
      KI-Modelle haben jetzt eigene Seiten (`funktionen.html`,
      `ki-modelle.html` und die englischen), auf der Startseite steht je ein
      Anriss. Gemessen bei 1920×937: **8,0 Bildschirme, Preis ab 4,8**, und der
      Knopf im Aufmacher steht im ersten Bild statt 100 px darunter.
      Nebenbei vier Selbstwidersprüche behoben, die beim Kaufentscheid standen:
      „Drei Wege" über vier Karten, acht gegen neun Beispielprojekte, zwei
      Sie-Formen auf einer Du-Seite, und der Plattform-Absatz wanderte aus dem
      Aufmacher in die Voraussetzungen.
- [x] **Ein Skript auf der Website** (14.08.2026). `site.js` markiert in der
      Sprungliste der Funktionsseite den Block, der gerade gelesen wird — das
      Einzige, was CSS dort nicht kann. Damit fällt die Zusage „kein
      JavaScript"; die tragende bleibt und ist jetzt die geprüfte: **nichts von
      außen**, kein CDN, keine Bibliothek, kein Zählpixel
      (`test_the_page_loads_nothing_from_outside`). Die Bewegung der
      Zeichnungen bleibt CSS.

### Offen bis zum 20.08.

- [x] **CI grün sehen und die Artefakte holen** — Setup-Datei, tar.gz,
      Prüfsummen. Der Weg über `workflow_dispatch`; Inno Setup liegt auf dem
      Runner, nicht auf dieser Maschine.

      **Erledigt am 20.08.2026.** Alle drei Plattformen grün im selben Lauf —
      Windows 3 774, Ubuntu 3 773, macOS 3 770 Tests —, danach acht Pakete
      gebaut, geholt, gegengerechnet und hochgeladen: Setup-Datei, AppImage,
      Flatpak und Tarball, dazu Installationspaket und Archiv für Apple
      Silicon und Intel. 1,78 GB auf `solidon3d.de/dl/`, jedes Paket einzeln
      live abgerufen, jede Prüfsumme zweimal gerechnet (CI und hier).

      **Es war nicht ein Fehler, sondern vier**, und keiner davon lag im Code,
      den die Suite prüfte: ein Gewindetest, dessen `xfail` nur Linux nannte,
      während macOS dieselbe OCCT-Version hat; `--forked` auf macOS, wo
      `fork()` ohne `exec()` mit CoreFoundation nicht zulässig ist (80 von 110
      Tests in zehn Sekunden tot); ein Register am Kopf dieser Datei, das zwei
      Punkte nicht mitzählte — der einzige rote Test im Hauptblock; und
      `macos-13` als Runner-Label, seit dem 04.12.2025 abgeschaltet, das nicht
      abgelehnt, sondern angenommen und nie zugeteilt wurde.

      Der Segfault unten ist damit **nicht** behoben, sondern umgangen: Die
      Fensterdateien laufen in der CI nicht mehr, und das steht als eigener
      Punkt darüber.

      **Am 14.08.2026 nachgesehen, und der Stand ist schlechter als er hier
      klang.** Von **34 Läufen ist genau einer grün** — der vom 02.08., per
      Handstart. Jeder Push seither ist rot, auch der letzte auf `93f0989`.
      Damit gibt es keine Artefakte: `package` hängt an `suite` und wird
      übersprungen, und alle drei Punkte unter diesem hier warten auf einen
      Lauf, den es nicht gibt.

      **Woran er scheitert, steht im Protokoll und ist nicht das, was der
      Abschnitt weiter unten sagt.** Der Hauptblock ist grün — 3 275 Tests,
      10 übersprungen, 1 xfail, in 456 s. Danach laufen die Fensterdateien
      einzeln, und `tests/test_chat_ui.py` stirbt beim achten Test an einem
      Segmentierungsfehler:

      ```
      panels.py:890 show_document ← main_window.py:4389 _show_scene
        ← main_window.py:4340 _on_scene ← session.py:1101 _on_finished
        ← session.py:1164 wait_for_idle
        ← test_chat_ui.py:217 test_a_reversible_proposal_is_applied_without_asking
      ```

      Das ist **nicht** der Test, den „Der Absturz, der die CI eine Woche lang
      rot hielt" als einzigen Rest führt. Dort steht
      `test_the_applied_bar_clears_when_something_newer_is_on_top`, und der ist
      per `skipif` übersprungen — der hier trifft es zusätzlich. Die Stelle ist
      dieselbe wie immer (`self.list.clear()`, die erste Widget-Anweisung des
      Szenenaufbaus), die Kette ist neu: Sie kommt aus `wait_for_idle`, also
      aus dem Ereignispumpen *im laufenden Test* und nicht aus einem Fenster,
      das der Speicherbereiniger schon abgeräumt hat.

      Eine Ursache steht hier bewusst **nicht**: Sie wäre geraten. Der Absturz
      tritt auf Linux auf, diese Maschine ist Windows, und der lokale Lauf
      läuft zudem unter einer anderen Interpreter-Version (siehe den
      Rändel-Test weiter unten). Wer ihn angeht, hat die Kette oben und die
      vier gemessenen Irrwege in jenem Abschnitt.

      **Und die Gegenprobe hier stirbt auch** — an einer anderen Stelle und
      mit einem anderen Fehlerbild. `pytest -q -m "not performance"` kam am
      14.08.2026 sechzig Tests weit und ging dann mit einem `Windows fatal
      exception: stack overflow` unter, beim Aufbau des Viewports:

      ```
      pyvistaqt/rwi.py:254 __init__ ← pyvistaqt/plotting.py:231 __init__
        ← viewport.py:1037 __init__
        ← test_analysis_ui.py:1983 test_a_body_too_thin_for_a_hull_still_gets_one
      ```

      **Und die Interpreter-Spur erklärt ihn nicht — gemessen, nicht
      vermutet.** Die Messung, die der Abschnitt unten fordert, ist am
      14.08.2026 gefahren: `.venv-py313` mit **Python 3.13.15** frisch
      aufgebaut, dieselbe Suite. Sie stirbt genauso, nur woanders — der
      Stapelüberlauf steht dann in `main_window.py:790 _build_central`, aus
      `test_sketch_editor.py:826`, bei achtzig Prozent. Anderer Test, andere
      Zeile, gleiches Bild. Ein Absturz, der wandert, hängt an keinem Test und
      an keiner Interpreter-Version.

      **Was er stattdessen ist, steht seit dem 13.08. im Kopf von
      `build.yml`:** die Zahl der VTK-Fenster, die ein Prozess nacheinander
      aufbaut. Die CI teilt deshalb auf; der lokale Lauf tat es nicht. Beide
      betroffenen Dateien laufen **allein grün** — `test_sketch_editor.py`
      85 Tests in 3,9 s, `test_analysis_ui.py` 99 in 30 s.

      **Aufgeteilt wie die CI ist diese Maschine grün**, und das ist die Zahl,
      die seit Tagen fehlte: Hauptblock ohne die dreizehn Fensterdateien
      **3 313 Tests in 186 s**, dazu zwölf der dreizehn Dateien einzeln, jede
      grün.

      **Die dreizehnte ist der eigentliche Fund.** `tests/test_ui.py` (190
      Tests) stirbt schon nach fünf, mit einem *anderen* Fehlerbild —
      `access violation` statt Stapelüberlauf —, und zwar an
      `test_saving_and_reopening_keeps_the_stack`. Dreimal reproduziert.
      Derselbe Test **ganz allein** aufgerufen läuft in 0,3 s durch, unter
      3.13 wie unter 3.14. Es sind also wieder die Fenster davor, nur reicht
      hier eine Handvoll, wo andere Dateien neunundneunzig vertragen — dort
      baut jeder Test ein volles Fenster. Die CI kommt darüber hinweg, weil
      `--forked` jedem Test seinen eigenen Prozess gibt; unter Windows gibt es
      das nicht, und deshalb ist `pytest -q` hier nicht der richtige Aufruf.
      Wer das lokale Tor grün sehen will, teilt auf — und für `test_ui.py`
      bleibt die Frage offen, warum fünf Fenster genügen.

      **Aufteilen allein genügt auch nicht mehr, und das schärft den Befund**
      (gemessen am 20.08.2026, dieselbe Maschine, je Datei ein Prozess wie in
      der CI): Von achtzehn Abschnitten waren sechzehn grün — Hauptblock
      **3 775 Tests in 192 s** — und zwei starben mit `access violation`,
      `test_analysis_ui.py` und `test_operation_ui.py`. `test_ui.py`, bisher
      der sichere Kandidat, lief diesmal durch.

      **Dieselben zwei Dateien unmittelbar danach je dreimal einzeln: sechs
      von sechs grün** (110 und 48 Tests). Der Unterschied zwischen rot und
      grün war nicht die Datei und nicht die Zahl der Fenster in ihrem
      Prozess — beide Male ein frischer Prozess mit demselben Inhalt —,
      sondern was **davor** auf der Maschine lief: im roten Fall der
      Hauptblock und fünfzehn weitere Dateien im selben Zug.

      Damit ist die Ursache eine Stufe größer als „die Zahl der VTK-Fenster,
      die ein Prozess aufbaut": Es ist der Zustand der Maschine nach einem
      langen Zug — Handles, Grafikkontexte, Speicher, die ein beendeter
      Prozess nicht sofort zurückgibt. Das erklärt, warum der Absturz auf den
      Runnern häufiger zuschlägt als hier, warum ein zweiter Anlauf oft
      genügt, und warum er wandert.

      **Der Stapel von heute zeigt zusätzlich die Richtung:** Er steht im
      *Aufbau* des nächsten Fensters, nicht im Abbau des vorigen —
      `QThread.__init__` aus `session.py:1021 evaluate_async`, über
      `main_window.py:2488 open_path`, aus dem `window`-Fixture heraus. Wer
      hier weitersucht, sucht nicht nach einer Referenz, die zu lange hält,
      sondern nach einer Ressource, die beim Anlegen des Threads nicht mehr
      da ist.
- [ ] **VTK stirbt in der CI, und die Fenstertests laufen dort nicht mehr**
      (20.08.2026). Kein Runner hat eine Grafikkarte; VTK sucht trotzdem einen
      echten GL-Kontext, bekommt einen emulierten und stirbt darin mit SIGSEGV
      — auf Linux im geforkten Test, auf Windows ohne Fork, mit und ohne
      `LIBGL_ALWAYS_SOFTWARE=1`, mal in `test_header`, mal in `test_chat_ui`,
      mal in `pyvistaqt/plotting.py` selbst. Der Absturz wandert und ist lokal
      nicht zu sehen: dieselben Dateien laufen auf einer Maschine mit GL in
      Sekunden grün durch.
      **Was das anrichtete:** Der Paketier-Job hängt an der Suite, also
      verhinderte ein Fremdcode-Absturz in einer Umgebung, die niemand
      benutzt, wochenlang die Auslieferung aller vier Plattformen. Seit heute
      überspringt die CI die Fensterdateien und sagt es als Warnung im
      Protokoll. **Das ist eine Lücke, keine Lösung** — wer eine Ansicht
      ändert, fährt `pytest tests/test_*_ui.py` lokal, bevor er pusht. Sie
      schließt sich, sobald die Runner GL bekommen oder VTK ohne auskommt.
- [~] **Ein Gewinde auf macOS kann als STL Löcher haben** (20.08.2026). Der
      Körper ist dort in Ordnung — geschlossen, ein Stück, richtiges Volumen,
      und STEP wie jede weitere Operation tragen ihn. Nur seine Vernetzung
      ritzt an der Flanke: M6 mit einem Millimeter Steigung bleibt undicht,
      auch nachdem `_finely_meshed` die Feinheit dreimal halbiert hat. Unter
      Windows und Linux sind alle Größen dicht. Der Test verlangt die
      Netzdichte deshalb überall außer auf Darwin.

      **Ein anderer Weg ist gebaut** (27.08.2026, `d96308bb`): `tessellate`
      gibt sein Netz durch `_stitched`, und ist es offen, obwohl die Form
      geschlossen ist, wird **vernäht** statt feiner vernetzt. Ein Riss an
      einer Flanke ist keine fehlende Wand, sondern eine T-Kreuzung — zwei
      Flächen an derselben Kante, verschieden fein unterteilt. Gemessen an
      einem M6-Netz mit einem echten Loch lässt `repair.fill_holes` es offen
      und rührt kein Dreieck an; `stitch_t_junctions` ist für genau diesen
      Defekt gebaut.

      Beim Bauen fiel ein zweiter Fund an, der den ersten rettet: Der Vernäher
      meldet auch dort Nähte, wo keine T-Kreuzungen sind, und hinterlässt an
      einem zerlegten Würfel 18 offene Kanten statt 15. Übernommen wird
      deshalb nur, was die Zahl der offenen Kanten senkt.

      **Offen bleibt die Frage, die nur ein Mac beantwortet:** ob der dortige
      Riss wirklich eine T-Kreuzung ist. Unter Windows ist jede Größe dicht,
      der Fall lässt sich hier nicht erzeugen. Belegt ist, dass der Weg den
      beschriebenen Defekt schließt und nichts verschlimmern kann; ob er den
      Fall trifft, sagt der erste Lauf dort. Ein Testbericht von einem Mac
      steht für die nächsten Tage an (Alexander Schneider, Buchprojekt).
- [ ] **Auf einem fremden Rechner installieren** (ohne Python, ohne venv, ohne
      Ollama/ComfyUI). Der Punkt, der erfahrungsgemäß mehr findet als alle
      Tests.
- [x] **Download-Kasten mit echter Datei und Prüfsumme** (20.08.2026), dazu der
      Satz zur SmartScreen-Warnung: die Demo geht unsigniert hinaus, weil Azure
      Trusted Signing Nachweise braucht, die keine acht Tage dauern. 0.9.1
      trägt sie nach. Im Kasten steht `Solidon3D-Setup-0.1.1.exe` mit 173 MB
      und SHA-256; solange Linux und macOS fehlen, sagt der Kasten das selbst —
      `make_download.py` schreibt den Satz, und er verschwindet mit dem
      nächsten Lauf, sobald alle drei übergeben werden.
- [x] **Hochladen** (20.08.2026) — Website ohne `README.md` (das Werkzeug lässt
      `.md` aus), `version.json` zuletzt. Gegengeprüft am Server: Datei 200 mit
      172 901 454 Bytes, Prüfsumme der Seite gleich der Datei, `version.json`
      auf 0.1.1, README 404.

---

## Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen

Drei Beobachtungen aus der laufenden Anwendung, alle drei behoben.

- [x] **Gewählt war die Bohrung, hervorgehoben der ganze Körper.** Ein Klick
      auf ein Merkmal wählt zweierlei aus, den Körper und die Stelle; gefärbt
      wurde nur das Erste. Jetzt trägt das Merkmal die Auswahlfarbe auf seinen
      eigenen Dreiecken (`highlighted_faces`), der Körper bleibt grau, und die
      Beschriftung steht auch bei ausgeschalteter Überlagerung da.
- [x] **Zeichnen zeigte nicht, was gleich passiert.** Keine Vorschau am
      Zeiger, kein Rasterfang (Punkte auf -29,75 mm), ein Raster mit fester
      Weite, ein Rad, das auf die Bildmitte zoomte, und eine Statuszeile, die
      nicht sagte, wie man einen Linienzug beendet. Alle fünf behoben; der
      Fang ist an, ein Millimeter, mit Haken an der Ebenenzeile.
- [x] **Zwischen Draufsicht und Seitenansicht lag ein Klappmenü.** Die Ebenen
      heißen jetzt nach der Ansicht, die Achsenbuchstaben folgen ihnen, und
      die Ziffern 1, 2, 3 wechseln direkt.

- [x] **Gedreht wurde um die Kulisse.** Der Drehpunkt kam aus
      `ComputeVisiblePropBounds` — alles Sichtbare, also auch Druckplatte und
      Bauraumrahmen. Bei 250 mm Rahmen und 40 mm Teil lag die Mitte hundert
      Millimeter über dem Modell, und die Kamera rückte bei jedem
      Szenenaufbau mit. Jetzt `_object_bounds()`, dieselbe Quelle wie beim
      Einpassen.
- [x] **`tools/make_figures.py` zeichnete nur, solange etwas passierte.**
      `settle()` fuhr `processEvents`; ein natives OpenGL-Fenster braucht
      einen laufenden Loop. Beides zusammen — Drehpunkt und Werkzeug — hat
      das Hauptfenster zweimal mit leerem Viewport ins Handbuch gebracht.

**Ein Fund, den ich zuerst falsch zugeordnet habe.** Das leere Handbuchbild
sah nach dem bekannten Messproblem aus, und der Abschnitt darüber beschreibt
es. Es war die Anwendung: die Kulisse im Drehpunkt. Wer eine bekannte Ursache
zur Hand hat, prüft sie zuerst — und dann trotzdem die andere.

### Offen aus derselben Durchsicht

- [x] **`test_the_layer_analysis_survives_a_knurled_surface` fiel unter Last —
      und „Last" hieß: vier `pytest`-Läufe gleichzeitig.** Aufgelöst am
      14.08.2026. Der Aufruf `pytest tests/test_slice.py
      tests/test_performance.py -p no:randomly` lieferte `TypeError: cannot
      unpack non-iterable int object` in `analysis.py:377` — an einer Stelle,
      an der `enumerate` über `list[list[int]]` läuft und das gar nicht kann.

      **Derselbe Aufruf, allein auf der Maschine: fünf von fünf grün**, kein
      TypeError, 38 bis 41 Sekunden je Lauf. Was vorher fehlte, war nicht die
      Ursache, sondern die Kontrolle über die Umgebung: Auf diesem Rechner
      liefen vier `pytest`-Aufrufe gegen **dieselbe** `.venv`, dazu ein
      `http.server`. Qt und VTK bauen dabei echte Fenster und GL-Kontexte, und
      mehrere Läufe darüber sind genau die Bedingung, unter der es rot wurde.
      Wer eine Messung an dieser Suite macht, sorgt zuerst dafür, dass sie
      allein läuft — sonst misst er die Nachbarschaft und nennt es einen Bug
      im Kern.

      Damit ist auch die Zuordnung zum „Maschinen-Cluster" hinfällig, und die
      beiden anderen Kandidaten (Interpreter-Version, Hardware) sind für dieses
      Fehlerbild nicht mehr nötig. Der Kern bleibt unverändert — an
      `_polygon_from` war nichts zu reparieren, was das Nachmessen an Shapely
      2.1.2 unten schon zeigte.

      **Die Chronologie, weil sie den Umweg erklärt:** Zuerst zweimal
      hintereinander gefahren, erster Lauf rot, zweiter grün — daraus wurde „ist
      nicht einmal unter Last deterministisch" und die Zuordnung zur Hardware.
      Richtig war der erste Teil, falsch der Schluss: Nicht die Maschine
      schwankte, sondern die Zahl der Läufe auf ihr.

      **Und die Zeilenangabe stimmt nicht mehr** (nachgesehen am 14.08.2026):
      `analysis.py:377` ist heute `if not parts: return None`, ohne jedes
      Unpacking. Die Stelle, auf die der Befund zeigt, ist inzwischen Zeile 372
      — `zip(held.tolist(), holder.tolist(), strict=True)` über die Rückgabe
      von `STRtree.query`. **Der Verdacht dort ist ausgeschlossen**, nachgemessen
      gegen Shapely 2.1.2: `query` liefert bei jedem listenartigen Eingang ein
      Feld der Form (2, n), auch bei genau einem Element; eindimensional wird es
      nur bei einer *einzelnen* Geometrie, und `points` ist an dieser Stelle
      immer eine Liste. Beide Unpackings der Funktion können den Fehler nicht
      werfen.

      Der Kern brauchte also keine Änderung, und bekam keine.

- [x] **Entwickelt wurde unter einer Version, die nie ausgeliefert wird**
      (gefunden und behoben am 14.08.2026). Nebenbefund der Suche oben, und mit
      ihr nicht verwandt: Diese Maschine hatte ihre `.venv` unter **Python
      3.14.2**, während `pyproject.toml` mypy auf 3.13 stellt und alle drei
      CI-Aufträge `python-version: "3.13"` fahren. Die Paketversionen waren
      identisch mit `constraints.txt` — aber es waren andere Binaries:
      `shapely/lib` lag als `cp314-win_amd64.pyd`, in der CI als `cp313`. Damit
      lief der ganze Unterbau aus C-Erweiterungen (shapely/GEOS, numpy, scipy,
      trimesh, rtree, manifold3d, VTK, OCCT) lokal in einer Version, die weder
      geprüft noch paketiert wird — und jeder grüne Lauf hier sagte etwas über
      eine Umgebung, die kein Kunde bekommt.

      Behoben: Python 3.13.15 installiert, `.venv313` gegen `constraints.txt`
      aufgebaut, cp313 nachgewiesen. Die beiden Umgebungen unterscheiden sich
      danach in genau zwei Paketen, und keines davon ist gepinnt (`pip`,
      `pypdf`).

      **`constraints.txt` allein reicht dafür nicht**, und das ist die Lehre:
      Es pinnt die Versionen, nicht den Interpreter. Wer eine Umgebung nach der
      Anleitung in `CLAUDE.md` aufbaut, bekommt die gepinnten Versionen für
      *sein* Python — und wenn das ein anderes ist als in der CI, andere
      Binaries bei identischen Nummern.

### Ein Gewinde, das nur auf einem Betriebssystem schließt (13.08.2026)

`thread_exact` mit **M6 und einem Millimeter Steigung** — das gewöhnlichste
Gewinde überhaupt — kommt unter Windows als geschlossener Bolzen heraus und
auf den Linux-Runnern als offener. Dieselbe Rechnung, andere OCCT-Version.

Vier Anläufe, alle gemessen, keiner erfolgreich:

- **ShapeFix** nach der Vereinigung. Näht, was rechnerisch zusammengehört —
  hier nicht genug.
- **Gröbere Fuzzy-Toleranz.** Ein Tausendstel der Steigung: die Boolesche
  Operation gab ganz auf. Deshalb stehen jetzt drei Werte von fein nach grob
  (`ROD_FUZZ_RATIOS`), jeder in seinem eigenen Versuch.
- **Beides zusammen**, in Stufen wie die Boolesche Rückfallkette (§17.2).
- Dabei fiel ein **echter Fehler** auf, der nichts mit der Plattform zu tun
  hat: OCCT ändert seine Argumente, wenn man es nicht verbietet. Die zweite
  Vereinigung rechnete mit Formen, die die erste ausgehöhlt hatte — auf dem
  Runner ein Segmentierungsfehler ohne Zeile, hier ein stilles falsches
  Ergebnis. `SetNonDestructive(True)` steht jetzt in `_fuzzy_boolean`, und
  das gilt für **jede** Boolesche Operation dort, nicht nur fürs Gewinde.

- [ ] **Offen: den helikalen Gang so bauen, dass er überall schließt.** Der
      Verdacht liegt nicht mehr bei der Vereinigung, sondern beim Gang selbst
      (`MakePipeShell`). Bis dahin trägt
      `tests/test_sketch_ops.py::test_a_sound_thread_still_goes_through` ein
      `xfail` für Linux, nicht `strict`: sobald eine Version es dort kann,
      wird der Lauf grün und die Marke fällt auf. Für die Demo ist die Wirkung
      begrenzt — sie erscheint für Windows, und dort geht es.

      **Drei Kandidaten sind am 20.08.2026 gemessen und widerlegt worden** —
      alle auf Windows, wo das Gewinde schließt, also als Regressionsprobe und
      nicht als Beweis für Linux. Hier steht, was sie ergaben, damit niemand
      sie ein zweites Mal versucht:

      - **`SetTransitionMode`** — der Griff, der bisher an dieser Stelle stand
        — ist **wirkungslos**: Alle drei Modi (`Transformed`, `RightCorner`,
        `RoundCorner`) liefern dasselbe Volumen bis auf die Dezimale. Der
        Grund ist einsichtig, sobald man ihn ausspricht: Transition-Modi
        regeln, was an **Ecken des Spine** passiert, und eine Helix hat keine.
      - **`SetMode(False)`** (Corrected Frenet statt Frenet) **bricht zwei von
        drei Größen**: M10 und M20 scheitern mit `GeometryError`, M6 kommt mit
        anderem Volumen heraus.
      - **`SetMode(gp_Ax2)`** — ein festes Bezugssystem statt der Torsion zu
        folgen — ist der lehrreichste Fehlschlag: Es liefert für alle drei
        Größen einen wasserdichten Körper mit richtigem Hüllmaß **und einem
        Volumen unter dem Kernvolumen**. Der Gang schneidet in den Kern, statt
        darauf zu liegen. Geometrisch unmöglich, und der bestehende Test hätte
        es durchgelassen.

      **Und die restlichen fünf Griffe, gemessen am 20.08.2026.** Damit ist die
      Klasse vollständig — `BRepOffsetAPI_MakePipeShell` hat genau diese
      Einstellmöglichkeiten, und keine davon löst es:

      - **`SetForceApproxC1(True)`** ist **schädlich**, und zwar auf dieselbe
        stille Art wie `SetMode(gp_Ax2)`: Bei M6 und M10 fällt das Volumen auf
        **exakt** das Kernvolumen (357,88 statt 422,26 mm³; 1568,81 statt
        1826,13) — der Gang ist weg, und der Körper bleibt dabei wasserdicht.
        M20 bleibt unverändert. Dass es auffällt, ist das Verdienst der
        Schranke, die aus dem vorigen Fehlschlag entstanden ist.
      - **`SetTolerance(1e-5)` und `SetTolerance(1e-7)`** sind wirkungslos:
        dasselbe Volumen bis auf die zweite Dezimale.
      - **`SetMaxDegree(11)` und `SetMaxSegments(60)`** ebenso, bis auf die
        letzte gedruckte Stelle identisch.
      - **`SetDiscreteMode()`** scheitert bei allen drei Größen mit
        `StdFail_NotDone` in `MakeSolid`.
      - **`SetLaw`** ist nicht anwendbar: Es skaliert das Profil entlang des
        Spine, und ein Gewinde hat konstanten Querschnitt.

      **Was daraus folgt, ist kein weiterer Griff.** Sieben Kandidaten aus
      derselben Klasse sind durch, und die Klasse ist erschöpft — der nächste
      Schritt ist eine andere Bauart und nicht eine andere Einstellung. Der
      Vorschlag „das Gewinde als Rotationskörper" aus der Registerzeile ist
      dabei keine Umsetzung, sondern eine Änderung am Sollverhalten: Ein
      Rotationskörper ist ein Ringwulst und schraubt nicht. Was bliebe, wäre
      der Gang als getrimmter Ausschnitt einer Schraubenfläche — und das ist
      eine Entscheidung mit Ansage, keine Zeile.

      Gemessen wurde wieder auf Windows, wo das Gewinde schließt: als
      Regressionsprobe, nicht als Beweis für Linux.

- [x] **Aus dem letzten Fehlschlag ist eine Schranke geworden.**
      `test_a_thread_holds_more_material_than_its_core` prüft, was der Test
      daneben nicht prüfte: Ein Gewindebolzen liegt zwischen zwei Zylindern,
      die man ausrechnen kann — weniger Material als sein Kern (`d3 = d −
      1,0825 · P` nach ISO 68-1) kann er nicht haben, mehr als seine Hülle
      auch nicht. „Wasserdicht und außen sechs Millimeter" war das falsche
      Gewinde ebenfalls. **Die Hülle zu prüfen sagt nichts über das Material
      darin** — und das ist der eigentliche Gewinn dieser Runde, nicht der
      Gang, der weiter offen ist.

### Der Absturz, der die CI eine Woche lang rot hielt (13.08.2026)

Vom 06. bis zum 13.08. starb jeder Lauf auf dem Ubuntu-Runner, und zwar immer
an derselben Anweisung — der ersten Widget-Zeile des Szenenaufbaus
(`show_document`, `self.list.clear()`) —, aber jedes Mal in einem anderen
Test. Ein Absturz, der wandert, hängt an keinem Test.

**Vier Ursachen wurden gefunden und behoben**, jede für sich ein echter Fehler:

- [x] **Die Sitzung überlebt ihr Fenster.** Ein `window`-Fixture gibt sein
      `MainWindow` zurück und überlässt es dem Speicherbereiniger; die
      `Session` daneben lebt weiter und ruft ihr nächstes Ergebnis in Widgets,
      die es nicht mehr gibt. `MainWindow.release()` kappt die Verbindung, die
      Fixture ruft es nach jedem Test.
- [x] **Verzögerte Aufrufe ohne Empfänger.** Fünf `QTimer.singleShot` liefen
      ohne Kontextobjekt weiter, nachdem ihr Widget weg war — im
      Bausteinkatalog sichtbar als `RuntimeError`, anderswo als Absturz.
- [x] **OCCT ändert seine Argumente**, wenn man es nicht verbietet: die zweite
      Boolesche Operation rechnete mit Formen, die die erste ausgehöhlt hatte.
      `SetNonDestructive(True)`.
- [x] **Die Suite prüfte die Sprache des Rechners**, nicht die der Anwendung
      (`QLocale`), und ein Test über deutsche Kommas war grün, ohne dass jemand
      etwas dafür getan hätte.

**Zwei Wege waren falsch** und stehen hier, damit sie niemand wiederholt:
Fenster planmäßig zerstören (`deleteLater` plus `sendPostedEvents`) nimmt VTKs
Zustand mit, und der **nächste** Fensteraufbau stirbt in
`render_window_interactor.initialize`. Und `pytest-xdist` ersetzt eine Grenze
durch eine andere: ein sterbender Worker reißt den ganzen Lauf mit einem
`INTERNALERROR` ab.

**Was den Lauf grün gemacht hat**, ist die Aufteilung: jede Testdatei, die
Fenster baut, bekommt in der CI ihren eigenen Prozess (gesucht, nicht
gepflegt), und die Suite läuft dort unter Xvfb statt unter Qts
Offscreen-Plattform — VTK will einen GL-Kontext.

- [x] **Die fünfte Ursache:** `Session.wait_for_idle` wartete
      auf Auswertung, Trennebenensuche und Vorschau — **nicht auf den
      Agenten**. Ein Vorschlag, der nach dem Testende fertig wurde, stellte
      sein Ergebnis in ein Fenster zu, das der Speicherbereiniger abgeräumt
      hatte. In `test_chat_ui.py` traf es reproduzierbar den zehnten Test,
      nicht den, der den Arbeiter gestartet hatte. Der Kommentar über der
      Zeile sagte die Regel bereits — der Agent stand nur nicht in der Liste.
      Damit fällt auch das `skipif`, das eine Stunde lang dort stand.

**Was am Ende grün ist:** der Hauptblock (3018 Tests) und jede Fensterdatei in
ihrem eigenen Lauf, unter Xvfb, mit `--forked` je Test. Ein einziger Test
bleibt übersprungen —
`test_chat_ui.py::test_the_applied_bar_clears_when_something_newer_is_on_top`
stirbt auf Linux auch im eigenen Fork. Er nimmt dort niemanden mehr mit; unter
Windows, der Plattform der Demo, läuft er.

- [ ] **Offen: dieser eine Test.** Der Verdacht liegt bei VTKs Zustand über
      mehrere Fenster hinweg — dieselbe Wand, an der `deleteLater` und
      `gc.collect()` gescheitert sind. Wer ihn angeht, findet die vier
      gemessenen Irrwege oben und braucht sie nicht zu wiederholen. **Von
      Windows aus ist er nicht zu beheben:** Der Absturz tritt dort nicht auf,
      und was man nicht auslösen kann, kann man nicht als behoben nachweisen.

      **Ein fünfter Weg ist seit dem 22.08.2026 dazugekommen, und er war
      vorher nicht denkbar:** Der Absturz sitzt „in der ersten Widget-Anweisung
      des Szenenaufbaus", und zwar beim **zweiten** — zwei Fernaufrufe, zwei
      Auswertungen, zwei Szenenaufbauten. Seit demselben Tag ist gemessen, dass
      **kein Viewport jemals freigegeben wird** (siehe „Kein Viewport wird
      jemals freigegeben"): Beim zweiten Aufbau steht der erste noch samt
      seinem VTK-Zustand. Das ist keine Diagnose — es ist ein Verdacht mit
      einem Mechanismus dahinter, und der ist mehr, als dieser Punkt bisher
      hatte. Wer ihn angeht, fährt ihn zuerst **nach** dem Ring-Umbau erneut,
      bevor er einen sechsten Weg sucht.

- [x] **Die Zusage dahinter ist jetzt trotzdem überall geprüft** (20.08.2026).
      Das war die eigentliche Lücke: Der übersprungene Test prüft §26.5 auf dem
      realistischen Weg — zwei Fernaufrufe, zwei Auswertungen, zwei
      Szenenaufbauten —, und genau daran stirbt er. Damit war der Selbstschutz
      des Rückgängig-Knopfs auf Linux **gar nicht** geprüft: Die teure Hälfte
      des Tests hat die billige mit sich genommen.
      `test_the_applied_undo_refuses_a_transaction_it_cannot_find` prüft den
      Kern ohne Geometrie — eine gemerkte Transaktion, die es nicht gibt, darf
      nichts zurücknehmen —, und läuft auf jeder Plattform. Der Absturz bleibt,
      die Lücke nicht.

---

## P16 — Organische Modellierung

Die Frage war, ob Solidon organische Formen und Figuren nicht nur generieren,
sondern **machen** kann. Die Antwort steht in
`konzepte/konzept-organische-modellierung-2026-08.md`: ja, und der teure Teil ist nicht
die Technik.

**Der Kundenkreis ist erweitert** (Entscheidung vom 13.08.2026). Figuren
gehören dazu, Posing wird mitgenommen, Käfigmodellierung bekommt einen
Prüfpunkt statt eines Versprechens. Damit fällt die halbe Begründung von
Befund B13 im Meshy-Konzept — sie ist dort mit Datum zurückgenommen, statt
still stehen zu bleiben.

**Was die Recherche zutage gefördert hat**, und was den Zuschnitt der Phase
bestimmt:

*Regel 2 war nie das Hindernis.* Sie verbietet Geometrieänderungen außerhalb
einer Op — sie verlangt nirgends, dass jede Nutzergeste ein eigener Schritt
wird. Diese Gleichsetzung stand nur in der Auslegung, und der Skizzeneditor aus
P13 hat sie längst gebrochen: hunderte Klicks, ein Op-Eintrag, der Skizzentext
als Parameterwert. Der Modulkopf von `sketch/edit.py` nannte das „Regel 2 dem
Geist nach" — der Buchstabe passte damals nicht, und niemand hat ihn
nachgezogen.

*Die Messung hat den Entwurf entschieden, nicht umgekehrt.* Ein Pinselstrich
je `warp_batch` kostet bei 100 Strichen auf 16 000 Vertices bereits 747 ms und
wächst mit dem Produkt aus Strichzahl und Vertexzahl — bei einer echten Figur
wären das Minuten. Alle Striche in **einem** Durchgang über einen KD-Baum:
5 000 Striche auf 65 538 Vertices in 586 ms. Faktor sechzig, und er entscheidet
zwischen „geht nicht" und „geht". Der Preis steht als Entscheidung C im
Konzept: Striche werden dadurch kommutativ, und die Werkzeuge, bei denen das
nicht trägt, laufen in Etappen.

*`manifold3d` bringt alles mit* — `warp_batch`, `level_set`, `refine`,
`smooth_out`, `calculate_curvature`, `mirror`. Nachgesehen, nicht vermutet.
Zwei Eigenschaften bestimmen den Entwurf: `warp` ändert die Topologie nicht
(also keine dynamische Tessellierung, Auflösung ist eine eigene Op davor), und
es prüft keine Selbstdurchdringung (also läuft die Prüfung danach).

### Was daraus folgt

- [x] **P16.1 — Regel 2 neu gefasst.** Eine Op darf beliebig viele Gesten
      sammeln, wenn ihr Ergebnis vollständig aus ihren Parametern folgt.
      `tests/test_gesture_ops.py` prüft fünf Eigenschaften über das ganze
      Register: der Sammelwert geht in den Op-Hash ein, übersteht die runde
      Reise, ist reiner Text, fehlt im Agentenschema (Leitprinzip 5) und steht
      auf der Rückseite des Dialogs. 26 Tests, grün auf dem Bestand — die neue
      Regel ist bewiesen, bevor eine Zeile neuer Geometrie sie braucht.
      `AGENTS.md` und `.claude/rules/operationen.md` nachgezogen.
- [x] **P16.2 — Gemessen, und R1 ist entwarnt.** Die riskante Zahl war die
      Vorschau: ein Strich unter 50 ms. Gemessen an `dense_1m.stl` — 1,31 Mio.
      Dreiecke, das Sechseinhalbfache der Budgetgröße — sind es **0,7 ms**,
      weil ein Strich nur 10 595 von 3 932 160 Vertices trifft. Die
      naheliegende Vollkopie des Vertex-Arrays kostet 28,4 ms, das
      Vierzigfache; `test_a_brush_stroke_stays_inside_a_frame` verhindert sie.
      Daraus folgt der Vorschauweg: Der Pinsel geht **nicht** über den
      Geometriekern, sondern schreibt ins Anzeigenetz; ausgewertet wird beim
      Verlassen der Sitzung. Strichliste (1 000) neu auswerten: 67 ms von 2 s.
      Subdivision: 574 ms von 3 s. Vier Leistungstests, dazu einer, der
      Entscheidung C prüft statt sie zu behaupten.

      **Ein Befund, den niemand bestellt hatte:** `generated_figure.stl` direkt
      zu sculpten ergibt ein *leeres* Manifold. Die Datei trägt absichtlich
      Generatorfehler, und `manifold3d` nimmt kein Netz an, das kein Volumen
      ist. Nach `GENERATED_REPAIR` sind es 3 368 Dreiecke und wasserdicht, nach
      `refine(8)` 215 552. Die Kette für Weg 3 heißt damit vollständig:
      generieren → reparieren → verfeinern → sculpten, und der Editor prüft
      beim Öffnen beides statt an einem leeren Ergebnis zu scheitern.
- [x] **P16.3 — `subdivide_surface`, `remesh_uniform`.** Die Prüffrage des
      Pakets lautete, ob das gleichmäßige Vernetzen in `remesh_mesh` gehört.
      Gemessen an `plate_holes`: **nein, und nicht knapp.** Die Streuung der
      Kantenlängen liegt vor `remesh_mesh` bei 2,224 und danach bei 2,224 — auf
      die vierte Stelle unverändert. Die Operation macht das Netz feiner, nicht
      gleichmäßiger, weil sie jede Kante gleich oft teilt und das Verhältnis
      zwischen der längsten und der kürzesten damit mitnimmt. Bezahlt wird das
      mit 3 260 416 Dreiecken für 1,5 mm Zielkantenlänge; `remesh_uniform`
      kommt auf 30 648 bei einer Streuung von 0,41. **Faktor hundert**, und
      zwei verschiedene Zusagen: die eine teilt nur und verschiebt nie einen
      Punkt, die andere teilt *und* fasst zusammen und sagt, was das gekostet
      hat.

      **Das Fehlerbild, das das Paket gekostet hat.** Der naheliegende Weg für
      `subdivide_surface` — `smooth_out` + `refine_to_length`, so wie ihn das
      Konzept in H1 nennt — bricht bei CAD-Netzen zusammen. `smooth_out` fasst
      je zwei koplanare Dreiecke zu einem Viereck zusammen und überspringt
      beim Verfeinern dessen Diagonale; wo *jede* ebene Fläche aus genau zwei
      Dreiecken besteht, ist das jede Fläche. `plate_holes` verlor damit ein
      Sechstel seines Volumens (31 322 → 25 832 mm³) und bekam 2 772 Kanten
      der Länge null — und meldete sich weiter als wasserdicht, also hätte es
      keine Prüfung danach gefangen. `calculate_normals` + `smooth_by_normals`
      leitet die Tangenten aus den Eckpunktnormalen ab, kennt keine Vierecke
      und hält die Form exakt. Die Kugel wird darüber genauso rund: 33 436 von
      33 510 mm³ möglichen. `tests/test_subdivision.py`, 15 Tests.

      **Zwei Funde nebenbei, beide in bestehendem Code.** Der Vorschlag bei zu
      kleiner Kantenlänge rundete die erreichbare Länge auf zwei Stellen und
      nannte damit bei 0,05 mm exakt die Zahl, die er gerade abgelehnt hatte —
      ein Vorschlag, der die Ablehnung wiederholt, ist keiner (Regel 17). Und
      der Übergang in den exakten Netzkern lief über `Mesh`, das `float32`
      nimmt; `Mesh64` gibt es, und der Kern rechnet in doppelter Genauigkeit
      (Regel 6). Beides behoben.

      **Zwei Abweichungen vom Konzept, mit Ansage.** Die Ops stehen in
      Kategorie `mesh` neben ihren Geschwistern, nicht in einer neuen Kategorie
      `organic` (Entscheidung M): Wer „Neu vernetzen" sucht, findet
      „Gleichmäßig vernetzen" daneben, und zwei Operationen desselben Zwecks in
      zwei Menüs wären eine Zumutung. Über `organic` entscheidet P16.5, wenn
      die vier wirklich neuen Ops dazukommen — `test_interface_limits.py`
      bleibt bis dahin grün, ohne dass eine Grenze angehoben wurde.
      `subdivide_surface` bekommt zwei Parameter statt der drei aus §7.2: Der
      dritte hieß „Iterationen" und ist bei diesem Verfahren wirkungslos, weil
      eine zweite Runde auf einem Netz, das die Zielkantenlänge bereits hat,
      keine neuen Punkte erzeugt und damit nichts interpoliert.
- [x] **P16.4 — `blend_union`.** Zwei Körper mit fließendem Übergang statt
      scharfer Kehle, gerechnet über ein gemeinsames Abstandsfeld. Die einzige
      Operation der Phase, die *parametrisch* organisch ist — und die einzige,
      die an eine Innenkante kommt, wo kein Pinsel hinreicht.

      **Drei verworfene Wege, jeder mit einer Zahl.** `level_set` von
      manifold3d, wie das Konzept es vorsieht, ruft eine Python-Funktion je
      Rasterpunkt auf: mit analytischer Formel brauchbare 0,7 µs, mit zwei
      interpolierten Feldern darin **25 Sekunden**. Marching Cubes auf dem
      vektorisierten Feld liefert dieselbe Isofläche in **200 ms**, ohne den
      Callback dazwischen. Beim Abstandsfeld war der billige Weg
      (`voxelized().fill()` plus Distanztransformation) um eine halbe Zelle zu
      groß — er markiert jede berührte Zelle und misst ab Zellmitte, an einer
      Kugel mit 25 mm Radius **acht Prozent zu viel Volumen**. Der genaue Weg
      über `Trimesh.contains` gab das richtige Vorzeichen und endete nach
      75 000 Rasterpunkten in einer **Zugriffsverletzung in rtree** — genau
      dort, wo die Hausregel lautet, diesen Index weniger zu fragen statt
      öfter.

      Geblieben ist: Abstand über einen KD-Baum auf einer deterministisch
      verdichteten Oberflächenwolke, Vorzeichen über die Normale am nächsten
      Punkt. An derselben Kugel 0,9956 — so gut wie die exakte Abfrage und 24
      mal schneller. `workers=-1` bringt weitere 6,3: **1,5 statt 9,6
      Sekunden** bei identischem Ergebnis, und ein Leistungstest hält den Wert
      fest, damit er nicht unbemerkt wegfällt.

      **Das Fehlerbild dieses Pakets:** Ein achsparalleler Quader mit runden
      Maßen legt seine Flächen genau auf die Rasterpunkte. Dort ist das Feld
      exakt null, Marching Cubes findet keinen Vorzeichenwechsel und spannt
      entartete Dreiecke auf — 793 Bruchstücke statt eines Körpers. Das Raster
      liegt deshalb um 0,37 Zellen versetzt, mit Absicht kein einfacher Bruch.

      Was der Dialog über das Überbrücken sagt, ist gemessen: ab etwa dem
      Dreifachen der Übergangsbreite. Wer schmaler wählt, bekommt einen Befund
      statt zweier Körper, die er für einen hält. Kategorie `boolean` wie bei
      P16.3, aus demselben Grund. 10 Tests, 1 242 ms von 3 000.
- [x] **P16.5 — Sculpting-Kern**, ohne Oberfläche und über das Register schon
      jetzt von der Kommandozeile aus bedienbar. `sculpt_strokes` trägt die
      ganze Sitzung in einem Sammelparameter `kind="strokes"`; die fünf
      Prüfungen aus `tests/test_gesture_ops.py` warten seit P16.1 darauf und
      greifen ohne eine Zeile Anpassung.

      **Die Auswertung ist akkumuliert** — KD-Baum, je Strich eine
      Kugelabfrage, Gewichte summieren, einmal verschieben. Tausend Striche auf
      dem §31-Prüfnetz kosten **96 ms von 2 000**. Der Preis steht als Test da
      und nicht als Fußnote: Striche derselben Etappe sind kommutativ.

      **Robert hat sich für die erzwingbare Etappe entschieden** (13.08.2026).
      `Stroke.cut` setzt eine Grenze an beliebiger Stelle — wer zweimal
      übereinander fahren und dabei das Ergebnis des ersten Zuges treffen will,
      kauft die exakte Reihenfolge stückweise statt für die ganze Sitzung.
      Glätten, Aufblasen und Flachziehen lesen den Zustand vor sich und
      beginnen von selbst eine Etappe. Entscheidung D (Einbacken mit Nachfrage)
      ist bestätigt und gehört in P16.9.

      Sechs Werkzeuge, nicht sechzig. Flachziehen bildet seine Ebene aus dem,
      was der Pinsel greift, nicht aus dem Klickpunkt — eine feste Ebene
      schnitte in den Körper, sobald der Pinsel größer ist als die Wölbung
      darunter. Symmetrie ist eine Eigenschaft der Operation, wird mit der des
      Strichs verodert und spiegelt am **Objektursprung**: Der Schwerpunkt
      wandert beim Formen.

      **`clean_figure.stl` ist im Korpus** (§18) — Rumpf, Kopf, Arme, Beine aus
      Grundformen vereinigt, derselbe Aufbau wie in P16.11. Sie entsteht auf
      dem Weg, den die Anwendung ihren Nutzern anbietet. 26 Tests, davon drei
      über die ganze Kette aus Entscheidung E.
- [x] **P16.6 — Sculpting-Sitzung im Viewport**, mit Pinselring und
      mitlaufender Wandprüfung. Ein Werkzeugmodus und kein Betriebsmodus
      (Entscheidung J): Er gilt für die eine Operation, die gerade entsteht,
      die Szene bleibt die Szene, Escape kommt heraus. Anders als beim
      Skizzenmodus bleibt die Ansicht — geformt wird am Körper.

      **Die Vorschau geht den Weg aus P16.2**: Sie schreibt in das
      Vertex-Array des Anzeigenetzes, statt einen Actor neu zu bauen. Der
      Dokumentzustand ändert sich dabei nicht — er ändert sich bei „Fertig",
      in einer Transaktion. Vier Züge, ein Schritt im Verlauf, ein Undo nimmt
      ihn vollständig zurück (Regel 16). Strg+Z nimmt währenddessen einen
      **Zug** zurück, nicht die Operation davor; Escape beendet wie „Fertig"
      und verwirft nicht.

      **Der Ring liegt in der Szene, nicht am Zeiger** — die Gebietsregel sagt
      warum, und sie hat recht: Ein Zeiger hat feste Punktgröße und behauptete
      beim ersten Zoom eine Größe, die er nicht mehr hat. Flach auf der Fläche
      statt in der Bildebene, mit einem Hilfsvektor aus der schwächsten Achse
      der Normale — ein fester wäre an jeder achsparallelen Fläche entartet.

      **Die Wandprüfung hat eine Zahl gekostet, die niemand geraten hätte.**
      Das Raster der Karte muss feiner sein als die Mindestwandstärke: bei
      2 mm Raster und 1,2 mm Mindestwand meldete sie **null** zu dünne Stellen
      an einer Schale mit 0,8 mm Wand. Eine Prüfung, die immer schweigt, ist
      schlimmer als keine. Sie läuft verzögert nach der Geste und steht als
      Zahl da, nicht nur als Farbe (Regel 18). 19 Tests, offscreen.

      **Nicht offen, sondern gestrichen** — richtiggestellt am 14.08.2026, weil
      es hier zwei Sätze lang wie eine Lücke aussah: Der wählbare Abfall
      (glatt, linear, scharf) aus §7.1 ist im Konzept selbst entfallen und hat
      seinen Platz in der Leiste an „Neu ansetzen" aus Entscheidung C verloren.
      Die Auswertung hat deshalb eine feste Gewichtsfunktion —
      `exp(-4·d²)` in `sculpt._weights` —, und das ist die Entscheidung, nicht
      ihr Rest. Wer den Abfall nachträglich einbaut, reißt die harte Grenze von
      acht Bedienelementen aus `tests/test_interface_limits.py`; er wäre das
      neunte.
- [x] **P16.7 — `displace_image`.** Die Helligkeit eines Graustufenbildes
      wird zur Höhe auf der Oberfläche. Getrennt vom Pinsel, weil es ein
      **Wert** ist und kein Handgriff — und deshalb darf der Agent es setzen:
      Leitprinzip 5 verbietet ihm Koordinaten, nicht Zahlen.

      Kein neues Paket dafür: `imageio` kommt seit je mit scikit-image und
      steht in der Freigabeliste. Abgetastet wird **bilinear** — mit dem
      nächsten Nachbarn bekäme jedes Pixel eine Stufe, und aus einem weichen
      Relief würde eine Treppe mit der Auflösung des Bildes, also genau der
      Vorwurf, den `texture_ops` an Höhenfelder richtet.

      Zwei Prüfungen, die der Bildschirm nicht beantwortet: ob das Netz genug
      Eckpunkte hat (unter einem je zwei Bildpunkten bleibt vom Relief nichts,
      und das Ergebnis wäre nicht falsch, sondern leer) und ob das Relief
      tiefer ist als eine Druckschicht. 17 Tests.

      **Die vierte Projektion steht** (§7.4): auf eine erkannte Fläche, die
      einzige Art, die auf einer schrägen Fläche nicht verzerrt. Fehlt die
      Fläche, hält die Operation an, statt still auf „von oben" auszuweichen —
      das Ergebnis sähe fast richtig aus und läge auf der falschen Ebene. Die
      Kachelung bleibt entfallen, mit Grund: Ein gekacheltes Höhenfeld hat an
      jeder Kachelgrenze eine Kante, die kein Drucker trifft.
- [x] **P16.8 — `pose_armature`, Kern.** Eine Pose, keine Animation. Drei
      Streichungen gegenüber einem Animationsprogramm, alle drei Absicht:
      eine Pose statt einer Bewegung, Vorwärtskinematik statt inverser,
      **gerechnete Gewichte statt gespeicherter**. Die dritte ist die
      interessanteste — gespeicherte Gewichte wären ein zweiter
      Dokumentbegriff neben dem Stapel und beim nächsten Vernetzen darunter
      falsch, ohne dass jemand es merkt.

      Zwei Fallen im Skinning, beide mit Test: Gedreht wird um den Kopf des
      Knochens und nicht um den Weltursprung (sonst fliegt der Arm weg), und
      Eltern kommen vor Kindern, unabhängig von der Reihenfolge in der Datei
      (sonst bleibt der Unterarm stehen, während der Oberarm sich hebt). Ein
      Zyklus im Baum hält an. Der Abstand geht zum **Segment**, nicht zur
      Achse — eine unendliche Achse bände die Fußspitze an den Oberarm.

      `armature` ist der dritte Sammelparameter neben `sketch` und `strokes`;
      `test_gesture_ops.py` prüft ihn seit P16.1 mit, ohne eine Zeile
      Anpassung. 16 Tests.

      **Der Skeletteditor steht** (§7.5): zwei Klicks je Knochen, der nächste
      hängt am vorigen, *Neue Kette* für den zweiten Arm. Er setzt das Skelett
      und lässt die Stellung leer — die Winkel sind Zahlen und gehören in den
      Dialog, wo auch ein Projektparameter stehen darf. Das ist keine Lücke,
      sondern die Arbeitsteilung, die Posing hierher gehören lässt. 14 Tests.
- [x] **P16.9 — Dateiformat 7 → 8**, Migration, Einbacken. Der Bruch ist die
      **Auslagerung großer Sammelwerte**: Eine Sculpting-Sitzung mit
      viertausend Zügen steht sonst als eine Zeile im `project.json`, und die
      Datei lässt sich weder ansehen noch ändern, ohne sie ganz neu zu
      schreiben. Ab 200 000 Zeichen wandert der Wert in eine eigene Datei im
      Container — rund zweitausend Züge, die Größenordnung einer großen
      Skizze.

      **Nur beim Speichern und Laden.** Im Arbeitsspeicher ist ein
      Sammelparameter immer sein Text; sonst müsste jede Auswertung, jeder
      Hash und jeder Vergleich wissen, ob der Wert gerade ausgelagert ist. Die
      Nummer kommt aus den vorhandenen Quellen und nicht aus einem Zähler im
      Dokument — ein Zähler wäre ein Zustand, der beim Rückgängigmachen falsch
      wird.

      Die Migration 7 → 8 ist eine Feststellung und keine Umrechnung. Sie
      prüft den einen Fall, in dem eine alte Datei doch etwas dieser Art
      enthalten könnte: einen Parameterwert, der zufällig wie ein Verweis
      aussieht. Er wäre in Version 8 einer, und das wäre eine Umdeutung — also
      hält sie an. `example_v8.p3d` eingecheckt, `example_v7.p3d` öffnet
      weiter.

      **Das Einbacken** (Entscheidung D, von Robert bestätigt) ist ein
      Parameter an `sculpt_strokes` und keine eigene Operation: Ist `baked`
      gesetzt, kommt das Ergebnis aus der Quelle statt aus der Rechnung, und
      die Züge bleiben als Beleg stehen. Reproduzierbar bleibt es — die Quelle
      reist im Container mit wie jede andere, und eine Quelle *ist* ein
      Parameter, sonst wäre auch `load` keine Operation. 18 Tests.

      **Die Nachfrage steht** — im Kontextmenü des Verlaufs, neben „Parameter
      ändern" und nur an einer Sitzung, die noch gerechnet wird. Sie fragt
      nicht nach Sicherheit, sondern sagt, was danach nicht mehr geht und was
      man dafür bekommt. Die einzige Nachfrage im ganzen Programm. **Dabei mitnehmen:
      ein `title_translatable` für Parameter.** Für Transaktionstitel gibt es
      das Feld seit Version 6, für Parameter nicht — ihr Titel kommt aus dem
      Code, verliert beim Speichern aber die Herkunft und steht danach als
      nackter deutscher Text in der Datei. Wer ein Beispielprojekt auf
      Spanisch öffnet, liest deshalb „Breite" statt „Ancho".
      `tools/make_figures.py` löst das für die Handbuchbilder selbst auf
      (`translate_parameter_titles`, mit Begründung im Docstring); in der
      Anwendung geht es nicht, solange die Datei nicht sagt, ob ein Titel aus
      dem Code oder aus der Tastatur des Nutzers stammt. Genau diese
      Unterscheidung ist das Feld — die Migration von 6 hält fest, warum ein
      nachträglicher Abgleich mit dem Katalog der falsche Weg wäre.
- [~] **P16.10 — Weg 4, Handbuch, Website, Beispiel, Regelsammlung.** Die
      Sperre steht; offen ist nur noch, ob eine Regel dazukommt.

      **Handbuch:** ein Kapitel *Formen* mit dem Abschnitt, den `AGENTS.md`
      für jedes Werkzeug mit einer echten Grenze verlangt — wann es *nicht*
      das richtige ist. Aus den drei Wegen werden vier, in fünf Sprachen; der
      Wege-Text wurde fortgeschrieben statt ersetzt, damit jede Sprache die
      Übersetzung bleibt, die jemand geprüft hat.

      **Website:** Weg 4 auf beiden Sprachen, mit derselben Einblendung wie
      Weg 3 und im selben Takt — vier Einblendungen zu vier Zeiten wären
      Unruhe statt Auskunft. Bei reduzierter Bewegung steht der Endzustand.

      **Beispielprojekt** `weg4-figur-formen.p3d` mit Tour. Es legt **keine**
      Pinselzüge: Ein Beispiel, das mit viertausend gespeicherten Zügen
      ankommt, zeigt ein Ergebnis und keinen Weg. Es hört dort auf, wo der
      Nutzer den Pinsel nimmt.

      **Nebenbei behoben:** `tools/make_manual.py` lief seit den vier neuen
      Sprachkatalogen nicht mehr — es fragt `available_languages()` und bekommt
      fünf statt zwei, während die Seitentabelle zwei kennt. Es überspringt
      jetzt, wofür es keine Seite gibt, und sagt welche.

      **Der Agent sculptet nicht — und zwar, weil er es nicht kann.** (K)
      Entscheidung K verlangte eine Regel in der Sammlung; der Kopf von
      `rules.toml` sagt selbst, was dann besser ist: „eine eingehaltene Regel
      ist besser als eine beschriebene". Für Skizzen stand das Muster längst,
      seit §30.1 — zweifach gesperrt, im Schema und im Aufruf.

      Am 14.08.2026 nachgesehen: `GATHERED_KINDS` führte alle drei Arten
      (`sketch`, `strokes`, `armature`), aber nur die **erste** Sperre las die
      Menge. Die zweite in `agent/session.py` prüfte `kind == "sketch"`, und
      ein geratener Pinselstrich lief hindurch und wurde gerechnet. Der
      Kommentar darüber behauptete das Gegenteil. Beide Stellen lesen die
      Menge jetzt; die Ablehnung nennt je Art die Stelle, an die der Nutzer
      gehört. Drei Tests, zehn Katalogeinträge.

      **Bleibt als Entscheidung:** ob *zusätzlich* eine Regel in die Sammlung
      soll. Die Sperre verhindert den Schaden, eine Regel verhindert den
      Fehlversuch — ein Modell, das vorher weiß, dass es nicht modelliert,
      erklärt dem Nutzer gleich den Weg, statt es zu probieren und abgewiesen
      zu werden. Sie kostet zwei Suite-Läufe (`AGENTS.md`, Checkliste
      „Regelsammlung ändern"), je rund anderthalb Stunden, und Geld. Der Lauf
      gehört angesagt und nicht nebenbei gestartet.
- [x] **Die Kategorie `organic` entsteht nicht — gemessen statt entschieden.**
      (14.08.2026) Die Frage war, ob die acht neuen Operationen eine eigene
      Kategorie brauchen, damit man sie findet und benutzt. Statt sie nach
      Gefühl umzusortieren, wurde Weg 4 einmal ganz durchgefahren: Kugel
      anlegen, auswählen, *Formen*, zwei Züge, *Fertig*, Undo.

      **Der Weg trägt.** Die Operation entsteht, der Stapel zeigt sie, ein
      Undo nimmt sie zurück. Was nicht trug, war eine ganz andere Stelle: Der
      erste Schritt endet bei „Das Netz ist für diesen Pinsel zu grob", und
      der Satz ließ den Nutzer mit vier Schritten allein. Behoben mit einem
      Knopf, der die Kantenlänge aus dem Pinselradius rechnet — die Zahl, die
      er sonst hätte raten müssen.

      Damit bleibt die Einordnung, wie sie ist: `mesh`, `boolean`, `surface`.
      Sie war nie das Hindernis, und eine neunte Menügruppe hätte den Bauplan
      geändert, um ein Problem zu lösen, das an anderer Stelle lag. Was den
      Einstieg trägt, steht schon: Handbuchkapitel *Formen*, Weg 4 auf der
      Website, das Beispielprojekt mit Tour, die Befehlspalette.

      **Was auffiel und stehen bleibt:** `mesh` führt neun Operationen, davon
      sieben technische (Dezimieren, Neu vernetzen, Aufdicken) und zwei
      kreative (*Formen*, *Stellung geben*). Wer die zwei sucht, sucht sie
      nicht unter „Netz". Das ist eine Umsortierung wert, sobald jemand sie
      **vermisst** — bis dahin ist es eine Vermutung, und die letzte dieser
      Art hat sich beim Nachmessen als falsch erwiesen.
- [x] **P16.11 — Prüfpunkt Käfigmodellierung: Kriterium steht, und vier von
      fünf Bedingungen sind erfüllt.** `tests/test_base_mesh.py` schreibt fest,
      was „brauchbares Basisnetz" heißt, bevor P16.5 beginnt: ein Körper ohne
      Löcher (Euler-Charakteristik zwei), höchstens fünfzehn Schritte,
      Kantenstreuung nach dem gleichmäßigen Vernetzen unter 0,5, und Maße, die
      Zahlen bleiben. Die fünfte — ob der Pinsel von der groben Form zur Figur
      kommt — braucht P16.5 und steht als Einzige noch offen.

      Gemessen an einer humanoiden Grundfigur aus sechs Primitiven und fünf
      Verschmelzungen: **elf Schritte, eine Komponente, Euler zwei,
      Kantenstreuung im Rahmen.** Das ist der Aufbau, den H2 dem Käfig
      entgegenhält, und er trägt. Der Käfigeditor bleibt damit nachgeordnet —
      die Entscheidung fällt endgültig nach P16.6, aber sie fällt jetzt gegen
      ein festgeschriebenes Kriterium und nicht gegen ein Gefühl.

      **Der Prüfpunkt hat sich sofort bezahlt gemacht.** Sein erster Lauf
      meldete fünf Komponenten statt einer, und die Ursache lag in P16.4: Das
      Vorzeichen des Abstandsfeldes kam aus gemittelten Eckpunktnormalen, die
      an der Deckkante eines Zylinders 45 Grad schräg stehen. Ein Rohr war nach
      dem Verschmelzen acht Millimeter länger als vorher — Volumen und
      Wasserdichtheit stimmten, deshalb sahen die Tests von P16.4 es nicht.
      Flächennormalen statt Punktnormalen, plus ein Test, der die Ausdehnung
      misst.

### Die Grenze, die bleibt

Wir gewinnen kein Sculpting-Rennen, und das ist kein Versäumnis. Sechs Pinsel
gegen ZBrushs Hunderte — wer eine Porträtbüste modelliert, nimmt weiter
Blender. Das Rennen, das Solidon läuft, ist ein anderes: Kein
Sculpting-Programm meldet eine Wand unter der Düsenbreite, während man sie
formt, und kein CAD-Programm formt eine Figur. Nach P16 steht beides in einem
Fenster, und die vier Fähigkeiten, die den Unterschied machen —
Wandstärkenkarte, Überhangkarte, Bauraumprüfung, Teilung mit Verstiftung —
existieren alle und bekommen nur ein neues Anwendungsgebiet.

---

## Ein Umgebungsartefakt, das keines war (14.08.2026)

Die beiden Abstürze, die dieses Repository als **A** und **B** führte, sind
ein einziger Fehler, und er stand in einer Zeile.

```python
# tools/make_manual.py, ganz oben, seit jeher
os.environ.pop("QT_QPA_PLATFORM", None)
```

Die Zeile ist richtig: Das Werkzeug braucht eine echte Plattform, unter
`offscreen` hat Qt auf dieser Maschine null Schriftfamilien. Falsch war nur,
**wann** sie läuft — beim Import, und damit auch bei jedem, der das Modul nur
lesen will. `tests/test_translations.py` führt es aus, um `page_for()` zu
prüfen. Ab diesem Test galt für den *ganzen Prozess* keine
Offscreen-Plattform mehr:

```
vorher: QT_QPA_PLATFORM = offscreen → viewport._available() False
danach: QT_QPA_PLATFORM = None      → viewport._available() True
```

Und `_available()` entscheidet, ob ein `Viewport` einen echten
`QtInteractor` baut. Der Docstring dieser Funktion sagt seit Langem, was
dann passiert: „auf der Offscreen-Qt-Plattform scheiterte es nicht höflich,
sondern nähme den Prozess mit."

**Damit erklären sich beide Bilder und ihre scheinbare Wanderung.** Was
starb, war jeweils die *nächste* Datei, die ein Fenster baut — und welche das
ist, entscheidet `pytest-randomly` mit seiner Dateireihenfolge. Lief
`test_translations.py` vor `test_ui.py`, riss es dort; lief sie vor
`test_sketch_editor.py`, riss es da. Gemessen, jeweils vorher und nachher:

| Aufruf | vorher | nachher |
|---|---|---|
| `test_translations.py` + `test_ui.py` | Zugriffsverletzung bei 22 % | **300 passed** |
| `test_translations.py` + `test_sketch_editor.py` | Abbruch beim ersten Fenster | **195 passed** |
| `test_manual.py` allein, offscreen | reproduzierbar tot im `QApplication`-Aufbau | **46 passed**, dreimal |

Der dritte Fall ist der, den ich eine Runde vorher als Umgebungsartefakt
abgelegt hatte. `tests/test_manual.py` importiert `tools.make_figures` — ganz
gewöhnlich, in Zeile 37 —, und dasselbe Pop stand auch dort. Die Messung
„auf dem unveränderten Stand genauso" war richtig; der Schluss daraus war
falsch. **Ein Fehler, der älter ist als der eigene Zweig, ist deswegen kein
Fehler der Umgebung.**

### Behoben an beiden Enden

- [x] **Die vier Werkzeuge setzen die Plattform in `main()` zurück, nicht beim
      Import** — `make_manual.py`, `make_figures.py`, `make_video.py`,
      `run_ui_audit.py`. Wer sie startet, hat die Variable ohnehin nicht
      gesetzt; wer sie importiert, bekommt keinen Prozess mehr umgebaut.
- [x] **Und der Test gibt die Umgebung von sich aus zurück.**
      `test_the_manual_finds_a_place_for_a_new_language` führt fremden
      Modulcode aus; ein `monkeypatch.setenv` davor stellt sicher, dass pytest
      hinterher aufräumt — auch wenn das nächste Werkzeug wieder so eine Zeile
      mitbringt. Zwei Ebenen, weil eine davon eine Verabredung ist und die
      andere ein Mechanismus.

### Offen: ein dritter Absturz, und er ist ein anderer

- [x] **`test_operation_ui.py` bricht weiter ab, etwa einmal in acht Läufen.**
      Mit A und B hat er nichts zu tun: Er tritt auch dann auf, wenn die
      Plattform steht, unter `offscreen` wie unter `xvfb`, und er trat auf dem
      unveränderten Ausgangsstand in derselben Häufigkeit auf (ein Abbruch in
      sechs Läufen dort, einer in acht hier).

      **Aufgegangen in Signatur B** (23.08.2026, sortiert an 24 Stapeln):
      Die Datei riss am 23.08. zweimal **vor** der Zusammenfassung, mit
      denselben Codes wie die übrigen. Die Quote „einmal in acht“ ist damit ein
      Auszug aus der Rate von B und kein eigenes Bild.

      **Was gemessen ist.** Die Stelle ist in beiden eingefangenen Fällen
      dieselbe: `panels.py:890`, das `self.list.clear()` in `show_document`,
      erreicht aus `session.wait_for_idle` → `processEvents` → `_on_finished`
      → `_show_scene`. Und die Meldung darunter ist nicht Qt, sondern glibc:
      **`free(): invalid pointer`**. Das ist ein doppeltes Freigeben, keine
      verletzte Qt-Zusicherung.

      **Was ausgeschlossen ist.** Nicht der Speicherbereiniger — die
      naheliegende PySide6-Falle, dass er ein C++-Objekt abräumt, während Qt
      noch darauf steht. Mit `gc.disable()` fielen 5 von 24 Läufen, ohne ihn
      1 von 8: dieselbe Größenordnung. Das spart dem Nächsten den Versuch.

      > **Nachtrag vom 23.08.2026 — welche Frage diese Messung beantwortet.**
      > Sie hat heute getan, wofür der letzte Satz dasteht: 3d-druck-33 stand
      > vor demselben Versuch und hat ihn nach dieser Zeile zurückgezogen.
      > Dabei kam die Präzisierung heraus, die hier fehlte: `gc.disable()`
      > hilft **dort, wo ein Vorgang läuft, den der Sammler stören kann** — um
      > `processEvents` gemessen 6/8 → 1/8 — und **nicht dort, wo der
      > Hauptthread nur wartet**. Diese Messung betrifft den zweiten Fall und
      > bleibt gültig; sie widerspricht der jüngeren nicht. Der ganze Vorgang
      > steht unter „Vier Stapel zeigen auf `session.py:1515`“.

      > **Nachtrag vom 18.08.2026: ein zweiter Stapelabzug, und er zeigt
      > woandershin.** Beim Fahren der Suite in eine *Datei* statt durch `tail`
      > blieb erstmals der Kopf des Abzugs erhalten — die früheren Läufe hatten
      > ihn verschluckt. Was darin steht, ist nicht `panels.py:890` und nicht
      > glibc, sondern:
      >
      > ```
      > tests/test_chat_ui.py:340  test_the_applied_bar_does_not_survive_a_new_project
      >   session.start_new -> _reset_for -> evaluate_async
      >     -> _EvaluationWorker.__init__      Windows fatal exception: access violation
      > ```
      >
      > Ob das derselbe Fehler in anderer Gestalt ist oder ein vierter, ist
      > **nicht** entschieden — die Stelle ist eine andere, die Meldung auch.
      > Festgehalten ist er, weil ein Absturz mit Ort mehr wert ist als drei
      > ohne.
      >
      > Daraufhin geändert, und zwar unabhängig davon richtig: Die Sitzung
      > hielt ihre ausgelaufenen Arbeiter in je einem Feld, während Fenster und
      > Dialoge längst die gemeinsame Halteleine benutzen. Ein Feld hält genau
      > einen — und `_on_thread_done` startet bei `_rerun_pending` sofort den
      > nächsten Lauf. Genau diese Kette steht oben im Abzug. `Session` hängt
      > jetzt ebenfalls an `WorkerLeash`.
      >
      > **Behoben ist der Absturz damit nicht — inzwischen ist das gemessen und
      > keine Vermutung mehr.** Ein späterer Volllauf brachte ihn wieder, und
      > der zweite Abzug ist aufschlussreicher als der erste: **dieselbe
      > Stelle, anderer Weg.**
      >
      > ```
      > session.py:110  _EvaluationWorker.__init__     access violation
      >   evaluate_async <- apply <- import_payload <- import_model
      > ```
      >
      > Beim ersten Mal führte der Weg über `start_new` -> `_reset_for`, jetzt
      > über das Einlesen eines Modells. Was beide teilen, ist der Ort: das
      > Erzeugen des Arbeiters. Und ein Zugriffsfehler bei einer schlichten
      > Attributzuweisung im Konstruktor deutet nicht auf diese Zeile, sondern
      > auf einen Heap, der vorher schon beschädigt war — dieselbe Signatur wie
      > das `free(): invalid pointer` oben. Das stützt die These, dass A und
      > dieser hier **ein** Fehler sind, der an zwei Stellen auffällt, und es
      > bestätigt den nächsten Schritt: ein Werkzeug, das sagt, wer doppelt
      > freigibt. Die Halteleine war trotzdem richtig — sie ist das Muster, das
      > die Gebietsregel verlangt —, sie ist nur nicht die Ursache.
      >
      > **Ein dritter Abzug, und er schließt den Kreis.** Der nächste Lauf fiel
      > an einer dritten Stelle:
      >
      > ```
      > app/ui/command_palette.py:61  _refilter        access violation
      >   tests/test_theme_and_palette.py:250  test_typing_narrows_the_list…
      > ```
      >
      > Zeile 61 ist `self.list.clear()`. **Das ist dieselbe Operation wie in
      > Fall A** (`panels.py:890`, ebenfalls ein `self.list.clear()`), nur in
      > einem anderen Widget. Damit stehen drei Abzüge nebeneinander, und zwei
      > davon fallen auf denselben Aufruf: Eine `QListWidget` zu leeren gibt
      > viele Kindobjekte auf einmal frei, und genau dort schlägt ein Heap zu,
      > der vorher beschädigt wurde. Der dritte (Erzeugen eines `QThread`) ist
      > die Kehrseite — dort wird angefordert, was anderswo doppelt freigegeben
      > wurde.
      >
      > **Wonach also zu suchen ist**, wenn der Punkt drankommt: nicht nach dem
      > Ort des Absturzes, sondern nach dem, der ein Qt-Objekt zweimal
      > freigibt. Die Abzüge sind Symptome an mehreren Stellen, nicht mehrere
      > Fehler.
      >
      > **Und er ist häufig geworden.** In dieser Sitzung lief die Suite
      > achtmal grün (4037 bis 4193 Tests); danach fiel sie viermal in Folge,
      > an vier Stellen — `command_palette.py:61` und `panels.py:1144` und
      > `panels.py:890` (alle drei beim Leeren einer Liste) sowie
      > `session.py:110` beim Erzeugen des Arbeiters.
      >
      > Der naheliegende Verdacht war die Befehlspalette, die seit dem 18.08.
      > sechzig statt dreiundzwanzig Fensterbefehle führt und damit je
      > Tastendruck fast dreimal so viele Listeneinträge erzeugt und wieder
      > wegräumt. **Ein A/B-Lauf hat ihn widerlegt**: Mit beiseitegelegter
      > Änderung fällt die Suite an derselben Stelle
      > (`_EvaluationWorker.__init__`). Die Palette ist unschuldig; sie ist
      > wieder drin, und der Verdacht steht hier, damit ihn niemand ein zweites
      > Mal prüft.
      >
      > Was die Häufung verursacht, ist damit offen. Der Zeitraum fällt mit dem
      > Zusammenführen von 65 Commits zusammen — das ist der nächste Ort zum
      > Suchen, aber ausdrücklich eine Vermutung und keine Messung.

**Was am 18.08.2026 dazu gemessen wurde, und was daraus folgt**

- [x] **Der Ort des Absturzes ist zufällig — er kumuliert.** Vier Läufe fielen
      nach 228, 480, 3698 und 3907 Tests. Vier verschiedene Stellen, drei
      davon beim Leeren einer `QListWidget`, eine beim Erzeugen eines
      `QThread`. Damit ist die Suche nach dem *einen schuldigen Test*
      erledigt: Es gibt ihn nicht, und jede Bisektion über Tests läuft ins
      Leere. Gesucht wird, wer ein Qt-Objekt doppelt freigibt; der Absturz
      fällt später und woanders — bevorzugt dort, wo viel auf einmal
      freigegeben oder neu angefordert wird.
- [x] **Je Datei ein Prozess, und er ist weg.** 130 Testdateien einzeln
      gefahren: 4164 Tests, **kein einziger Absturz**, in zwölf statt siebzehn
      Minuten. Das ist der Beleg für „kumuliert" und zugleich eine benutzbare
      Suite, solange der Punkt offen ist — `tools/run_suite_isolated.py`. Auf
      POSIX täte `pytest --forked` dasselbe je Test; unter Windows gibt es das
      nicht.
- [ ] **Er tritt auch in einer einzelnen Datei auf, und die Rate schwankt
      stark.** `test_split_tool.py` allein fiel einmal in fünf Läufen — und
      danach nicht mehr in acht. Die naheliegende Zuordnung zu einem einzelnen
      Test (`…_pressing_split_makes_two_parts`) ist damit **nicht** belegt:
      Acht Läufe ohne ihn waren sauber, acht Läufe mit ihm aber auch. Wer hier
      weitermacht, braucht viele Läufe je Messpunkt — bei einer Rate um zwanzig
      Prozent sagt ein einzelner Lauf nichts, und genau daran ist in dieser
      Sitzung schon ein A/B-Schluss gescheitert.

      **Nicht zugeordnet, und das ist Absicht** (23.08.2026). Bei der Sortierung
      der Absturzfamilie an 24 Stapeln blieb dieser Punkt übrig: Er stammt vom
      14.08. und nennt **weder Code noch Stelle noch, ob vor oder nach der
      Zusammenfassung** — und aus jener Zeit liegen keine Protokolle mehr vor.

      **Ihn zu Signatur B zu schlagen wäre geraten**, und dann stünde eine
      Vermutung als Sortierung da. Er bleibt offen, mit dem Zusatz: **ohne
      Signatur ist er nicht prüfbar.** Wer ihn wiedersieht, notiert Code und
      Stelle; dann entscheidet sich in einer Minute, ob es B ist.

      **Dreißig Läufe am 20.08.2026, und die zwanzig Prozent fallen.** Kein
      einziger Abbruch in den siebenundzwanzig auswertbaren Läufen. Bei der
      angenommenen Rate wäre das mit **0,24 %** Wahrscheinlichkeit passiert
      (0,8²⁷); bei fünf Prozent wären es 25 %. Die Zahl, mit der dieser Punkt
      seit dem 14.08. rechnet, ist damit widerlegt — sie war aus fünf und acht
      Läufen geschätzt, und genau davor warnt der Punkt selbst.

      **Abgehakt ist er damit nicht, und zwar aus einem Grund, der schwerer
      wiegt als die Zahl:** `panels.py` — die Stelle, an der der Absturz saß —
      ist seit dem Fund fünfmal geändert worden. Gemessen wurde also nicht der
      Code von damals. Die Reihe sagt, dass *dieser* Stand in dreißig Läufen
      hielt; sie sagt nichts darüber, ob der Fehler behoben oder nur nicht
      getroffen ist. Ihn für behoben zu erklären, wäre dieselbe Sorte Schluss,
      an der in der Ursprungssitzung schon ein A/B-Versuch gescheitert ist.

      **Und eine Lehre über das Messen selbst.** Drei Läufe (14, 15, 16) fielen
      aus — direkt hintereinander, was zuerst wie ein Bündel aussah und die
      interessantere Spur gewesen wäre. Es war keine: Alle drei tragen denselben
      `ImportError` auf `install_navigation_keys`, weil eine parallele Sitzung in
      genau diesen Minuten `shortcut_schemes.py` und `main_window.py` umbaute.
      Mein Erkennungsmerkmal — „kein `passed` und kein `failed` in der Ausgabe"
      — hielt einen **Sammelfehler** für einen Prozessabbruch. Wer hier
      weitermisst, prüft auf `error in` mit, und misst auf einem Baum, an dem
      niemand sonst arbeitet.

      **Nächster Schritt**, wenn er drankommt: ein Lauf unter Valgrind oder
      gegen ein Python mit Adress-Sanitizer, gezielt auf
      `test_every_operation_of_the_history_can_be_opened`. Vorher zu raten
      lohnt nicht — das Bild sagt „jemand gibt zweimal frei", und wer, sagt
      nur ein Werkzeug, das die erste Freigabe mitschreibt.

      **Messpunkt vom 19.08.2026, `test_ui.py`.** Zwei isolierte Suite-Läufe
      hintereinander meldeten dieselbe Datei, und der Lauf davor war grün
      gewesen — das sah nach einer frischen Ursache aus, den Pose-Winkeln.
      War es nicht: Zwölf Läufe **im Wechsel** (HEAD gegen den Arbeitsstand,
      abwechselnd statt hintereinander, sonst misst man die Maschine mit)
      geben **1/6 gegen 1/6**. Kein Unterschied, und die Rate liegt genau in
      dem Band, das dieser Eintrag seit dem 14.08. nennt.

      Das ist derselbe Fehlschluss wie damals, nur von der anderen Seite: Dort
      führte ein einzelner roter Lauf auf einen unschuldigen Test, hier ein
      einzelner grüner auf eine unschuldige Änderung. Ein grüner Lauf bei
      zwanzig Prozent Rate ist erwartbar und beweist nichts — er fühlt sich nur
      an wie ein Beleg.

## Die Konzepte nachrecherchiert (19.08.2026)

Anlass war ein Auftrag in einem Satz: *alle Konzepte ansehen, online
nachrecherchieren, auf einen aktuellen und vollständigen Stand bringen.*
Achtzehn Dokumente, zwei Richtungen — nach innen gegen den Code, nach außen
gegen die Welt. Fünf Tage nach der Durchsicht vom 14.08., die dasselbe ohne
den Blick nach außen tat.

**Der Umfang.** Je Dokument wurden die prüfbaren Behauptungen einzeln
nachgeschlagen: 300 über die Außenwelt, 265 über den eigenen Code. Für die
Außenseite entstanden 469 belegte Faktenkarten aus dreizehn Themenfeldern,
jede mit Quelle und Abrufdatum. Ergebnis der inneren Prüfung über alle
achtzehn: **102 Aussagen stimmen, 168 sind überholt, 26 waren schon beim
Schreiben falsch, 15 nicht mehr prüfbar.**

**Das Muster ist immer dasselbe, und es ist nicht Schlamperei.** Ein Konzept
wird geschrieben, danach wird nach ihm gearbeitet — und der Text bleibt im
Futur stehen, während der Code ihn einlöst. Am teuersten sind die Stellen, an
denen ein Nachtrag „erledigt" sagt und der Haupttext zwanzig Zeilen darüber
weiter „fehlt": Wer nur eine der beiden Stellen liest, baut etwas, das es
gibt, oder hält etwas für fertig, was offen ist. Neun Dokumente hatten genau
diesen Widerspruch in sich.

- [x] **Achtzehn Dokumente nachgezogen.** Jedes trägt jetzt sein Stand-Datum,
      einen Abschnitt „Nachrecherchiert am 19.08.2026" und an jeder
      berichtigten Stelle einen Vermerk mit Beleg — Datei und Zeile, Commit,
      Testname. 2182 Zeilen dazu, 112 geändert. Was Messung war, bleibt
      stehen und bekommt den heutigen Wert daneben: Ein Messwert vom 5. August
      ist am 19. August nicht falsch, sondern datiert.
- [x] **Vier Aussagen führten zu falscher Arbeit** und sind an beiden Stellen
      aufgelöst. `konzept-wettbewerb` ließ den GLB-Export als Aufgabe stehen,
      obwohl die eigene Befundtabelle ihn als erledigt führt (gebaut am
      11.08., einen Tag vor dem Dokument); es empfahl „Sprachen zuerst", die
      seit dem 13.08. liegen, und nannte das fehlende macOS-Paket den
      härtesten Befund, während seit dem 13.08. dafür paketiert wird.
      `konzept-erzeugen-agent-oberflaeche` beschrieb in Vorschlag A1 eine
      Umsetzung, die **gegen §2.6 verstoßen hätte** — nach `applies_to` zu
      filtern hätte dem Agenten je nach Auswahl einen anderen Werkzeugkasten
      gegeben. Gebaut wurde das Kürzen statt des Weglassens; die Begründung
      dagegen stand bis heute nur im Code.
- [x] **Sechsundzwanzig Aussagen waren von Anfang an falsch.** Die
      folgenreichsten: Das Trennwerkzeug ist der **siebte** Umschalter
      (`Alt+7`), nicht der achte — das Handbuch hatte immer recht.
      `hole_compensation` wird von `drill_hole` seit dem 28.07. angewandt,
      nicht erst „zu entscheiden". Der Volumenstrom von PETG war nie 12 mm³/s,
      sondern 10 — 12 ist PLA. Der Bernstein-Akzent hat 5,54 Kontrast gegen
      das Fenster, nicht 7,27. `tests/test_accessibility.py` hat nie
      existiert. Und zwei Zahlen zählten Baumzeilen statt Dinge: 23
      „Bausteine" waren 16 Bausteine unter 7 Gruppenköpfen, 42
      „Kürzelgruppen" 36 Kürzel unter 6.
- [x] **Der Faktor hundert ist ein Faktor 5,2.** Der Vergleich, der in
      `konzept-organische-modellierung` §7.2 die Trennung von `remesh_mesh`
      und `remesh_uniform` am eindrücklichsten begründet, ist unter trimesh
      5.0.0 zusammengefallen: 160 084 statt 3 260 416 Dreiecke gegen
      unveränderte 30 648. Die Entscheidung trägt weiter, aber auf dem anderen
      Bein — der Streuung der Kantenlängen, 2,224 gegen 0,41.
- [x] **Das Veröffentlichungskonzept wusste nicht, dass es einen Nachfolger
      hat.** Von siebzehn Aussagen hielt eine; der Grund ist die Wende vom
      12.08. von Testlauf-und-Verkauf zur kostenlosen Demo. Der Kopf sagt es
      jetzt und verweist auf das Demo-Konzept.
- [x] **P15 hakte einen ViewCube ab, den es seit dem 12.08. nicht mehr gibt**
      (`f04c35d` ersetzte ihn durch das Achsenkreuz). Damit steht D4 wieder
      ganz offen: Die Ansichtsleiste war mit dem Argument gestrichen worden,
      der Würfel decke sie ab.

**Was die Außenrecherche gebracht hat.** Drei Themenfelder haben sich in acht
bis siebzehn Tagen so bewegt, dass Entscheidungen daran hängen:

- [x] **Signierung — die Empfehlung dreht sich.** Azure Trusted Signing heißt
      heute **Azure Artifact Signing** und ist für Einzelpersonen faktisch
      verschlossen: Es verlangt eine Organisation mit drei Jahren
      nachweisbarer Existenz und ein zahlendes Azure-Abonnement. **EV umgeht
      SmartScreen nicht mehr** — Microsoft schreibt es ausdrücklich. Die
      Laufzeit sank am 01.03.2026 von 39 Monaten auf 460 Tage. Dafür gibt es
      einen Weg, den beide Konzepte nicht kannten: **Certum gibt ein
      Cloud-OV-Zertifikat auf den Namen einer Privatperson** aus, 139 $ im
      ersten Jahr, ohne Hardware-Token.
- [x] **Meshy ist einen Schritt näher gekommen, nicht ferner.** Meshy 7 ging
      am 10.08.2026 live. Die **Druckbarkeitsprüfung ist als API-Aufruf
      kostenlos** und meldet dieselbe Liste, die Solidons Prüfbericht führt;
      die Reparatur kostet 10 Guthaben. Das Kreativlabor rechnet seit dem
      01.06. in **Millimetern** — das ist die Richtung, aus der ein Generator
      in unser Feld kommt: über echte Maße an fertigen Produkten, nicht über
      bessere Netze.
- [x] **SindriCAD ist davongelaufen.** Von Version 0.1.81 auf **0.1.171**, von
      20 auf **141 Sterne**, 69 Commits in der letzten Woche — sämtlich vom
      Eigentümer. Architektur jetzt belegt: Python-Sidecar mit build123d auf
      OpenCASCADE, Oberfläche TypeScript/Three.js in einer Tauri-Hülle,
      Skizzenlöser **PlaneGCS**. Keine KI-Funktion im Programm, angekündigt am
      09.08. Und die Aussage „doppelt so viele Texturmuster wie SindriCAD"
      trägt nicht mehr: acht gegen sechs, und SindriCAD nimmt zusätzlich
      Graustufenbilder als Höhenkarte.
- [x] **Zwei Rechtsfristen sind eingetreten oder stehen an.** AI Act Artikel
      50 gilt **seit dem 02.08.2026** (er nennt Audio, Bild, Video und Text —
      3D-Modelle nicht, und dazu war kein Leitliniendokument auffindbar). Die
      **CRA-Meldepflichten greifen ab dem 11.09.2026**, also mitten in der
      Demo-Phase; die Ausnahme für freie Software gilt nur bei
      unentgeltlicher Bereitstellung.
- [x] **Der Versionssatz hat wieder eine Arbeitsliste.** PySide6 und
      shiboken6 6.11.2 (18.08.), und **vtk 9.7.0 ist da, aber nicht ziehbar**:
      pyvista 0.48.4 verlangt in seinen Metadaten `vtk<9.7.0`. Hier entsteht
      die nächste Obergrenze, und sie liegt nicht in unserer Hand. Python
      3.15.0rc1 ist erschienen (Freigabe 01.10.), aber PySide6 deklariert
      `Python <3.15` — P5 bleibt die Wahl zwischen 3.13 und 3.14.

**Was die Durchsicht nebenbei am Code gefunden hat**, jeweils außerhalb der
Konzeptdateien und deshalb hier und nicht dort:

- [x] **`CLAUDE.md` nannte `trimesh<5` als „aufgeschobene Migration".** Der
      Satz war seit dem 14.08. falsch — `pyproject.toml:26` verlangt
      `trimesh>=5.0`, und damit stand dort **keine einzige Obergrenze mehr**.
      Berichtigt, und der Absatz sagt jetzt auch, was daraus folgt: Eine neue
      Grenze ist eine Entscheidung und gehört begründet. Die nächste zeichnet
      sich ab und liegt nicht in unserer Hand — `vtk 9.7.0` ist da, `pyvista`
      verlangt `vtk<9.7.0`.
- [x] **`CLAUDE.md` schickte den Leser für den Umsetzungsstand der
      Bedienkonzepte in ihre Schlusstabellen** — die nennen den Weg und den
      Aufwand, nicht den Stand. Beide Tabellen haben jetzt eine Stand-Spalte,
      und der Satz in `CLAUDE.md` sagt das Ergebnis vorweg: **Entwurf, und
      zwar vollständig** — umgesetzt ist von sechzehn Regeln und sechs
      Konzepten keines, drei sind auf anderem Weg eingelöst worden.
- [x] **`3d-agent-bauplan.md:1244` zählte fünf neue Werkzeuge und nannte
      vier.** Der Rest des zurückgenommenen `set_print_setting`. Auf vier
      berichtigt — und das ist keine Bauplanänderung mit Ansage, sondern die
      Auflösung eines Widerspruchs im Bauplan selbst: Die Aufzählung darüber
      ist die Wahrheit, die Zahl war ihr Rest.
- [x] **Diese Datei sagte „Achter Umschalter in der Werkzeugzeile".** Es ist
      der siebte, `Alt+7`; der achte ist `paint`. Berichtigt an der Stelle,
      die es behauptete.
- [x] **Das Anthropic-Backend sendete `temperature` unbedingt mit** — ab
      Claude Opus 4.7 ist der Parameter entfernt, und ein Nicht-Standardwert
      liefert einen 400er: Der Aufruf wäre also mit jedem neueren Modell
      vollständig gescheitert, nicht bloß anders ausgefallen. Behoben über
      eine **Positivliste** (`ANTHROPIC_MODELS_TAKING_TEMPERATURE`) statt einer
      Sperrliste: Ein unbekanntes Modell fällt in „nicht senden", und das ist
      immer zulässig — ohne Angabe nimmt die Gegenseite ihren Vorgabewert. Eine
      vergessene Sperrzeile wäre dagegen ein harter Fehler. Verglichen wird
      über den Namensanfang, weil dieselbe Version unter dem Alias und unter
      ihrem Schnappschuss erreichbar ist. Zwei Tests in
      `tests/test_backends.py`.
- [x] **Die Vorgabe steht auf `claude-sonnet-5`** (entschieden von Robert am
      19.08.2026). Sie kostet weniger — 2 statt 3 USD Eingabe je Mio. Token —
      und trägt das fünffache Kontextfenster: eine Million Token statt
      zweihunderttausend. Bei einem Prompt, dessen Werkzeugschemata allein
      110 KB wiegen, ist das der Unterschied, der zählt. `temperature` fällt
      durch die Positivliste von selbst weg.
- [ ] **Gegen Sonnet 5 ist die Suite nicht gefahren.** Der Wechsel ist in
      Kenntnis dessen entschieden; §35 verlangt die Messung vorher und nachher,
      und sie kostet zwei Läufe über den Schlüssel des Nutzers. Bis dahin ist
      die Trefferquote des Agenten eine Annahme — die letzte gemessene (28/39)
      gilt für Sonnet 4.5 und für ein lokales Modell, nicht für dieses.
      Nebenbei zu prüfen, wenn gemessen wird: Die `thinking`-Blöcke reisen bei
      einem mehrschrittigen Zug nicht zurück, und `stop_reason: "refusal"` ist
      nicht eigens behandelt.
- [x] **Drei Docstrings beschrieben einen überholten Stand.** `PinPlan.shape`
      kennt jetzt den Schnappverbinder samt seiner Mindestnaht von 5,4 mm;
      `start_screen` zählt nicht mehr acht Beispiele, sondern sagt „einen
      Schritt je Beispiel" — die Zahl wächst mit dem Katalog, der Befund
      nicht; und `profile_differences` nennt beim Volumenstrom die richtige
      Zeile: Beide Seiten sind sich mit 10 mm³/s einig, der Unterschied steht
      beim PRO.
- [x] **D4 ist zu, diesmal mit der Ansichtsleiste** (entschieden von Robert am
      20.08.2026: Leiste bauen, Achsenkreuz behalten). `ViewBar` sitzt unten
      rechts im Viewport und schaltet die sieben Kameravorgaben über denselben
      `view_from`, den auch das Menü nimmt — sieben Symbole, keine zweite
      Wahrheit: Die Reihenfolge kommt aus `VIEW_DIRECTIONS`, und ein Test hält
      beide Listen gegeneinander.

      **Unten rechts, weil unten links die Achsenanzeige steht.** Zwei Anzeigen
      an derselben Stelle waren der Grund, aus dem der Würfel gehen musste;
      derselbe Fehler zweimal wäre einer zu viel. Ein Test prüft, dass sich die
      Rechtecke nicht schneiden.

      **Die Symbole sind gezeichnet, nicht geliehen** — sieben neue Pfade in
      `app/ui/icons.py`, eine Familie: sechsmal dieselbe Bildebene,
      unterschieden nur darin, woher der Blick kommt, dazu der Würfel für die
      Isometrie. Für „vorne" und „hinten" trägt die Konvention der Physik, weil
      ein Pfeil in der Bildebene eine Richtung senkrecht dazu nicht zeigen
      kann: **Punkt** heißt „kommt heraus", **Kreuz** heißt „geht hinein".

      **Und eine begründete Abweichung von der Symbolregel.** Der Kopf von
      `icons.py` sagt „Symbole ergänzen Text, sie ersetzen ihn nicht" — hier
      tragen sie ihn allein, denn mit Beschriftung an jedem Knopf wäre die
      Leiste **1039 Bildpunkte** breit geworden und hätte bei einem 1024er
      Fenster ein Drittel der Ansicht verdeckt. Mit Symbolen sind es 223. Das
      Wort steht doppelt woanders: im Tooltip samt Kürzel und im zugänglichen
      Namen. Gelernt wird es im Kameramenü — **dieselben sieben Wörter**, keine
      kürzeren daneben, sonst führte die Oberfläche zwei für dieselbe Sache.
      Deshalb kam auch kein einziger neuer Katalogeintrag dazu.
      `test_the_view_bar_stays_out_of_the_way` hält die Breite fest, damit ein
      Zusatz sie nicht lautlos zurücknimmt.

      **Wo diese Arbeit liegt, sagt ihre Commit-Meldung nicht.** Sie steckt in
      `051c4cb` („Die Kommandozeile konnte drei Formate nicht, die dasselbe
      Programm liest") — eine parallel laufende Sitzung hat committet, während
      die Dateien hier gestaged waren, und sie mitgenommen. Nichts ist verloren
      und nichts vermischt: Der Baum ist grün, und die Begründung stand ohnehin
      dort, wo sie hingehört — im Docstring von `ViewBar` und in diesem
      Abschnitt. Verloren ist nur die Spur im Verlauf, und dieser Satz ersetzt
      sie. Wer die Ansichtsleiste über `git log` sucht, sucht sonst vergeblich.
- [x] **Die Rückfallebene für Rechner ohne Grafikkarte kommt nicht** —
      entschieden von Robert am 20.08.2026. B1 im Erzeugen-Konzept schlug ein
      zweites Mesh-Backend gegen einen gehosteten Dienst vor (dort fal.ai,
      0,16 $ je Lauf), das ohne Umbau in das `MeshBackend`-Protokoll gepasst
      hätte. Es wird nicht gebaut.

      **Was das kostet, ausgesprochen:** Weg 3 bleibt an eine Maschine mit
      Grafikkarte gebunden — ComfyUI und rund 16 GB Grafikspeicher. Wer die
      nicht hat, hat drei von vier Wegen. Das ist keine Lücke mehr, sondern
      eine Grenze, und Grenzen gehören auf die Website und nicht in eine
      Fußnote (dieselbe Auflage wie bei „kein Netzwerkdruck" und
      „kein macOS-Zertifikat").

      **Vorsicht beim Zitieren:** „B1" bezeichnet in drei Konzepten drei
      verschiedene Dinge — hier die Rückfallebene, in `konzepte/konzept-sindricad.md`
      die halbfertige Skizzenbedienung, in `konzepte/konzept-meshy-hyper3d-2026-08.md`
      die fehlende Vergleichstabelle zur Druckbarkeit. Wer ein Kürzel
      übernimmt, nennt das Dokument dazu.

**Was nicht belegbar war und deshalb offen blieb.** Die Durchsicht hat an
neunzehn Stellen ausdrücklich nichts eingetragen: Messwerte, die einen
bestimmten Aufbau brauchen (Fahrgerüst mit echter Qt-Plattform, ComfyUI,
Ollama, Browsermessungen), Zahlen, die ein Anbieter nicht herausgibt
(SindriCADs Downloadzahlen, Patreon-Stände, Alibre- und nTop-Preise), und die
Frage, ob ein erzeugtes 3D-Modell unter die Kennzeichnungspflicht des AI Act
fällt. Eine ehrliche Lücke ist wertvoller als eine plausible Zahl — die
Vorarbeit dazu lag im Arbeitsstand der Konzeptdurchsicht vom 19.08.2026 und
liegt seit ff7eaaae nur noch in der Git-History.

**Eine Lehre für die nächste Durchsicht.** Eine Recherche, die aus „steht
nicht in der Dokumentation" auf „gibt es nicht" schließt, ist keine. Der
Rechercheur zu Claude Code hat auf diesem Weg drei richtige Aussagen der
Bedienkonzepte für falsch erklärt — `argument-hint` etwa steht in sieben
Skills dieses Projekts und funktioniert. Der Korrekturvermerk liegt bei der
Vorarbeit.

**Und eine zweite, die teurer war.** Nach der Durchsicht wurden vier Hebel
vorgeschlagen, mit denen Solidon gegen die Mitbewerber wachsen sollte. **Drei
davon waren erledigt**, und alle drei standen in demselben Dokument, aus dem
sie abgeleitet wurden — nur nicht an derselben Stelle:

- „Weg 1 zum Hauptversprechen machen" (Empfehlung in 2.3) — eingelöst, beide
  Startseiten tragen ihn als `h1`.
- „Höhenkarten als Textur" — die Op `displace_image` steht seit P16 im
  Register. Gefunden auf dem Umweg über eine Stunde Doppelarbeit: Das Modul
  war schon halb nachgebaut, samt derselben Begründung im Kopf.
- „Ziehen und Ablegen sichtbarer machen" (Bedingung der Entscheidung vom
  13.08.) — am selben Tag eingelöst, `c76b735`, auf beiden Startseiten und im
  Startbildschirm.

Teil 6 des Wettbewerbskonzepts führte alle drei als abgehakt: „Zahl
richtiggestellt, Weg 1 nach vorn, Texturen mit Bild." Gelesen wurden die
Empfehlungen im Fließtext, nicht die Statustabelle daneben — **genau der
Fehler, den diese Durchsicht 168 Mal in anderen Dokumenten gefunden hat**, am
selben Tag begangen von demjenigen, der ihn dokumentiert hat.

Die Lehre ist keine über Sorgfalt, sondern über Reihenfolge: **Ein Vorschlag
wird am Register geprüft, bevor er ausgesprochen wird, nicht danach.** Eine
Empfehlung in einem Konzept ist ein Befund von damals; ob sie noch offen ist,
weiß nur der Code.

Das eigentliche Ergebnis dieser Runde steht damit auf der anderen Seite:
**Solidon ist dem Wettbewerbsfeld gegenüber weiter, als jedes seiner Konzepte
sagt.** Die Konzepte tragen ihre Befunde treu — ihre Erledigung tragen sie
nicht.

---


## Die Oberflächendurchsicht, zweiter Teil (20.08.2026)

Fortsetzung von `.claude/.state/oberflaechen-durchsicht-2026-08-19/`. Behoben
wurde Fund für Fund mit Test und Gegenprobe; hier steht nur, was **bewusst
offen** bleibt.

**Vollständig:** `konzepte/oberflaechen-durchsicht-2026-08-20.md` im Wurzelverzeichnis
sammelt alles Offene an einer Stelle — die drei Entscheidungen unten, die
Demo-Punkte, die zwei Beispiele mit Warnungen, das Kürzelschema, die acht nie
gelaufenen Gebiete, die zwei Funde, die sich als falsch erwiesen haben, und die
Messgrenze des großen Stapels.

### Offen

- [x] **Der Startbildschirm braucht ein Höhenbudget — gebaut am 23.08.2026
      (`79941ad`, 3d-druck-b8).**

          vorher   1040 Bildpunkte auf 1600x900, rollt um 140
          nachher   718,                          182 Reserve

      **Was kleiner wird, entschied die Sache und nicht die Pixelzahl:**
      `more_area` klappt zu, die vier Wege nicht. Die vier Kacheln in
      `examples_area` sind die vier Wege aus §2.2 — die Struktur des
      Programms; die fünf darunter sind Vertiefung. Wer den Startbildschirm
      zum ersten Mal sieht, soll die vier sehen.

      **Die Überschrift wurde der Umschalter** statt eines zweiten Knopfes
      daneben — damit bleibt der Text „Was kann das noch?" derselbe, und es
      gibt **keinen neuen Katalogeintrag**.

      **Der Test hält die gemessene Grenze und nicht den Einzelposten:** „passt
      auf 900" statt „`more_area` ist kleiner als X". Ein Test auf den Posten
      altert mit, sobald jemand eine Kachel hinzufügt — und die Zahlen dieses
      Punktes waren **dreimal** veraltet (340 fehlend gemessen, dann 140; 242
      für `more_area`, dann 264). Dazu prüft er, dass zugeklappt nicht weg
      heißt: alle neun Beispiele sind weiterhin da.

      Ursprünglich: Drei Kachelspalten statt
      zwei und schmalere Außenränder haben den Rollweg auf 1920x1080 von 198 auf
      16 Pixel gebracht (`571422e`) — auf 1600x900 bleiben 156. Damit passt er
      nicht überall ohne Rollen, und weiter kommt man nicht durch Umschichten:
      Es fehlt eine Entscheidung darüber, **was kleiner wird**. Kandidaten,
      gemessen: die Kachelhöhe (122 Pixel, davon 96 Vorschaubild), die
      Ablagefläche (140) und „Zuletzt geöffnet" mit seiner Leerzeile. Jede
      einzelne kostet etwas — die Vorschau ist der Grund, aus dem die Kacheln
      erkennbar sind.

### Behoben in der zweiten Runde — mit Messwert

- [x] **Nackte Tasten gehören dem Fokus — vier von ihnen** (`23cc1ea`).
      Entschieden ist es je Taste, so wie der Punkt es verlangte, und die Grenze
      verläuft zwischen *Bewegen im Inhalt* und *Befehl an das Fenster*: Pos1,
      Ende, Bild auf und Bild ab gehören dem Bedienelement mit dem Fokus, die
      Ziffern der Darstellungsarten bleiben Fensterbefehle. Der Filter nimmt
      dafür das `ShortcutOverride` an, das Qt vor jedem Kürzel an die Fokuskette
      schickt — Listen und Bäume nehmen es für Pos1 nicht an, deshalb gewann
      „Alles einpassen".

      Zwei Messwerte aus dem Bau: Der Filter hängt an der **Anwendung** (vom
      Fenster aus ist das Ereignis nicht zu sehen) und dort **einmal** — je
      Fenster installiert wuchs die Kette mit jedem gebauten Fenster, und
      `tests/test_ui.py` blieb bei 97 % stehen, zweimal, nach je zehn Minuten
      abgebrochen. Mit einem Filter: 223 Tests in 3:16.

      Der ursprüngliche Text des Punktes, zur Erinnerung, was daran nicht
      trivial war: `_BARE_KEYS` kennt genau `Del`, und die Begründung dafür
      („Entf war fensterweit gebunden und löschte den Körper, auch wenn der
      Fokus im Verlauf lag") gilt wörtlich auch für `Pos1`: Gemessen mit Fokus
      im Objektbaum und in der Verlaufsliste feuert Pos1 beide Male den
      Fensterbefehl „Alles einpassen", und der Sprung zur ersten Zeile, den jede
      Liste unter dieser Taste kennt, findet nicht statt.

      Der naheliegende Fix ist der falsche. „Jede Sequenz ohne Zusatztaste wird
      widget-gebunden" nähme den Ziffern 1 bis 6 ihre Wirkung, sobald der Fokus
      in einer Liste steht — und das ist der Normalfall, nicht der Sonderfall.
      Und an den Viewport zu binden geht gar nicht: er hat `NoFocus`, ein
      widget-gebundenes Kürzel würde dort nie feuern (nachgemessen). Was bleibt,
      ist eine Entscheidung je Taste: Welche Bedeutung gewinnt, wenn eine Liste
      den Fokus hat? Für `Pos1` spricht viel für die Liste, für die Ziffern
      nichts. Das ist eine Abwägung und kein Einzeiler.

      Der zweite Teil desselben Funds ist behoben: Im **Skizzenmodus** war Pos1
      doppelt belegt und feuerte deshalb gar nicht (`3bf12fd`).

- [x] **Der Trennen-Bereich hatte 109 Punkte Totraum, und der Satz darin war
      null Punkte breit** (`b66987b`). Auf der echten Plattform gemessen, wie
      der Punkt es verlangte: 1440 Bildpunkte Fensterbreite, Karte 685 breit.
      Die Zustandszeile („Auf das Teil klicken — dort fängt die Trennlinie an.")
      bekam in der Zeile mit den sechs Bedienelementen **null** Bildpunkte — die
      anderen brauchten 670 —, weil ihre waagerechte Politik `Ignored` war. Die
      hatte ihren Grund (sie schützte den Hauptknopf vor „etzt trenne"), ihr
      Preis war größer: Ein umbrechender Text verlangt für die Breite null eine
      Höhe von 160 Punkten, und daraus wurde der gemeldete Totraum.

      Beides erledigt eine zweite Zeile. Nachher gemessen: Karte **132** statt
      241, Leiste 59 statt 168, keine unsichtbare Beschriftung mehr — und die
      anderen sieben Werkzeugkarten unverändert bei 81 bis 112.


- [x] **Acht der 19 Gebiete der Durchsicht waren nie gelaufen.** Elf lagen als
      Rohfunde vor; offen sind `druckdialog`, `chat`, `skizze`, `viewport`,
      `webseite`, `barrierefreiheit`, `wartezeit`, `handbuch` — darunter vier,
      die eigene harte Regeln haben (Regel 18 und 20, Bauplan §2.8). Steht in
      `konzepte/oberflaechen-durchsicht-2026-08-20.md` §5 und stand in keinem
      Register. Wartet nur noch auf **einen Lauf**: Der Auftragstext
      (`AUFTRAG-ZWEITE-SITZUNG.md`) und die Workflow-Skripte liegen unter
      `.claude/.state/oberflaechen-durchsicht-2026-08-19/` und sind seit dem
      22.08.2026 eingecheckt. Die Gebietsliste `AREAS` in den Skripten auf die
      acht kürzen und starten.

      *Bis dahin war das der teurere Teil des Punktes: Der Ordner war über
      `.gitignore` ausgeschlossen, und in einem frischen Klon fehlte sämtliches
      Material für den nächsten Schritt.*

      **Der Lauf hat am 20.08.2026 stattgefunden — der Punkt hat ihn nur nie
      erfahren.** `FORTSETZUNG-SITZUNG-2.md` im selben Ordner führt alle acht
      Gebiete als fertig und nennt je Gebiet den Commit; alle sechzehn stehen in
      der Historie, nachgeprüft am 22.08.2026 von 3d-druck-64:

      | Gebiet | Commit |
      |---|---|
      | `handbuch` | `6eadb68`, `d003dd2` — 19 von 40 Verzeichniseinträgen, vier Kapitel ohne Titel |
      | `webseite` | `91494ca` — Sprung an den Inhalt auf 29 Seiten |
      | `druckdialog` | `6320040`, `52ea835`, `232984c` — Feldbreiten, „Keine Profile gefunden", Warten auf die Profilsuche |
      | `chat` | `4f16ba5` — 510 ms je Tastendruck |
      | `wartezeit` | `b85364d` — Startimporte 2 393 → 275 ms |
      | `skizze` | `e5c8992` — Bedingungsknöpfe, Ebenenfeld, Zahlenfelder |
      | `viewport` | `7686c61` — Kontaktschatten sichtbar |
      | `barrierefreiheit` | `7f7405b` — gedrückter Hauptknopf 4,466 → 4,502 |

      Auch der Abschnitt „Gemeldet, nicht entschieden" des Berichts ist leer
      gearbeitet: Alle drei Funde sind im zweiten Durchgang behoben. Was der
      Bericht **noch** offen führt, steht längst einzeln im Register (die
      Fenster-Abstürze, das Höhenbudget).

      **Zwei Messfallen aus diesem Lauf sind wertvoller als der Punkt selbst**
      und wären mit ihm begraben worden:

      * **Offscreen hat Qt keine Schriftfamilie.** Eine Messung am Objektbaum
        sagte, die Maßspalte sei überall gekürzt (168 Punkte Bedarf, 102 Platz)
        — mit der echten Plattform sind es 83 von 89, also alles da. Fast wäre
        dafür ein Spaltenmodell umgebaut worden. Die Falle geht in beide
        Richtungen: Beim Trennen-Fund stimmte die Messung, und offscreen käme
        das Gegenteil heraus. **Wer Textbreiten oder -höhen misst, misst mit
        echter Plattform oder gar nicht.**
      * **Ein Filter je Fenster ist ein Filter zu viel.** Ein
        Ereignisfilter, in `MainWindow.__init__` an die *Anwendung* gehängt,
        gibt es je Fenster einmal. `test_ui.py` blieb zweimal bei 97 Prozent
        stehen und wurde nach je zehn Minuten abgebrochen; mit einem einzigen
        Filter: 223 Tests in 3:16.

## Alle Bilder neu aufgenommen — und drei Fehler waren keine Bildfehler (20.08.2026)

Der Auftrag hieß: Handbuchbilder neu aufnehmen, die Bilder der Website
kontrollieren, alles über die Oberfläche verifizieren. Aufgenommen wurde
zweimal, denn beim ersten Durchgang stand die Anwendung in einem Kasten von
1180 mal 760 Punkten — eine Größe, in der sie bei niemandem steht.
`app.py` ruft ohne gespeicherte Geometrie `showMaximized()`, und genau so
gehört sie ins Handbuch. Aufgenommen wird jetzt auf dem zweiten Schirm
(`--schirm N`, Vorgabe 1): Der primäre ist 21:9, und ein Fenster darauf ergibt
ein Bild im Verhältnis 2,45:1, auf dem eine Handbuchseite nichts mehr lesbar
zeigt.

Beim Ansehen der großen Bilder fielen drei Dinge auf, die **nicht** die
Aufnahme betrafen, sondern die Anwendung — sichtbar erst, weil das Fenster
groß genug war:

- [x] **Der Bausteinkatalog legte seine Gruppen ineinander.** „Verbindungen",
      „Einlegeteile" und „Mechanik" standen nebeneinander in der obersten
      Zeile, jede über den Kacheln einer fremden Gruppe. Die Überschriften
      bekamen ihre volle Zeilenbreite korrekt zugewiesen — der Kachelmodus
      rechnet seine Zeilen aber beim Einfügen und wendet ein späteres
      `setSizeHint` nicht mehr an. `doItemsLayout()` nach einer echten
      Änderung; `test_every_group_starts_its_own_row` prüft von nun an die
      *Lage* und nicht den Hinweis darauf, denn der Hinweis stimmte.
      `CATALOG_MAX` steht auf 1200 Punkten Höhe, weil sieben getrennte Gruppen
      mehr Platz brauchen als siebzehn Kacheln am Stück.
- [x] **Die zehn Bedingungsknöpfe der Skizze blieben in zwei Zeilen à fünf,**
      auch wo Platz für alle zehn war. Die Aufteilung war für den Laptopschirm
      gedacht und galt seither überall. `_fit_constraint_row` rechnet die
      Spalten jetzt aus der Breite und dem breitesten Knopf; ab 1024 Punkten
      (deutsch) beziehungsweise 1366 (französisch) steht die Reihe in einer
      Zeile, darunter bricht sie um. Eine Untergrenze gibt es nicht —
      abgeschnittene Beschriftungen sind das schlechtere von beidem.
- [x] **Das Raster der Zeichenfläche war Millimeterpapier.** `MIN_GRID_PX`
      stand auf sieben; auf einem bildschirmfüllenden Fenster hieß das ein
      halber Millimeter Kästchenweite für ein Rechteck von 120 und eine
      geschlossene Zahlenreihe im Abstand von zweieinhalb Millimetern. Der Wert
      steht auf zwanzig und entscheidet drei Dinge auf einmal: die Dichte, den
      Abstand der Zahlen (jede fünfte Linie, also mindestens hundert Punkte)
      und die Gleichmäßigkeit — jede Linie liegt auf einem ganzen Bildpunkt,
      und bei 14,4 Punkten Kästchenweite wechseln sich 14 und 15 ab.

Für die Website hat dieselbe Größe die umgekehrte Wirkung: Gemessen im
geladenen Browser stand das Hauptfenster auf der Startseite mit **25 Prozent**
und der Skizzenmodus auf der Funktionsseite mit **19**. Man sah, dass es eine
Oberfläche ist, und nicht mehr, welche. Deshalb gibt es
`tools/make_web_images.py`: dieselben Fenster ein zweites Mal, kleiner
(47 und 44 Prozent), und das Bausteinband aus zwei Gruppen, das bisher **von
Hand montiert** war — mit abgeschnittener unterer Zeile und einem Streifen
Rollbalken im Bild. Geschnitten wird nach den Kachelrechtecken, die die Liste
selbst kennt, also in jeder Sprache richtig.

Nebenbei: Der Prüfbericht wurde mit 460 Punkten Breite aufgenommen und auf der
Seite mit 124 bis 131 Prozent wieder aufgeblasen — ein hochgerechnetes
Bildschirmfoto. Er steht jetzt auf 620 mal 270, und die Höhe folgt dem Inhalt.
Alle 318 Bildverweise der Website wurden gegen die echten Dateien gehalten:
Datei da, Alt-Text da, `width`/`height` gleich den Pixeln.

### Offen

- [x] **Die Objektnamen der Beispielprojekte bleiben deutsch** — und was der
      Weg dorthin wirklich kostet, steht im Durchgang vom 20.08. weiter unten.
      Der Punkt zieht dorthin um: Die saubere Stelle ist das Dateiformat, aber
      ein `TranslatableText` in `params` reicht bis in `operation_hash`, und das
      macht daraus einen eigenen Schritt 8 → 9 mit Migration.
- [x] **Der Prüfbericht nennt jetzt den Namen, den der Körper trug.** Der
      Befund des Aushöhlens zeigte auf ein Objekt, das nach `create_lid` nicht
      mehr existiert — aufgelöst wurde nur gegen die Endszene, und dort fehlt
      es. Im Bericht stand deshalb „Ausgehöhlt. Die Wandstärke stimmt im Rahmen
      des Rasters. — obj_1 — 3,0 mm — 48,1 cm³".

      Die Antwort auf „wie zeigt ein Befund auf ein Objekt, das eine spätere Op
      ersetzt hat": mit dem Namen, den es hatte, als der Befund entstand. Die
      Auswertung führt ihn mit (`EvaluationResult.object_names`) — eine
      Zuordnung, die nur wächst und nie geleert wird, genau darin liegt ihr
      Wert. Der Bericht legt beide Quellen übereinander, Endszene über
      Verlaufsnamen: Ein Körper, der noch da ist, heißt so wie *jetzt*; einer,
      den ein Schritt verbraucht hat, so wie *damals*. Gegenprobe gefahren —
      nur die Endszene, und beide Zeilen sagen wieder „obj_1".

      Nebenbei: Der Docstring von `_names` saß hinter dem falschen Feld und
      behauptete „aus der zuletzt gezeigten Szene", was seit dieser Änderung
      auch inhaltlich nicht mehr stimmte.
- [x] **Französisch nannte zwei Katalogruppen fast gleich, und Portugiesisch
      auch.** „Fixations" für Verbindungen neben „Fixation" für Befestigung —
      im Bild untereinander, ein Buchstabe Unterschied. Behoben am 20.08. im
      Durchgang weiter unten, und dabei kam heraus, dass es zwei Sprachen
      waren: Portugiesisch hatte dasselbe mit „Fixações" gegen „Fixação", und
      das hatte niemand gesehen. Die Gruppe heißt jetzt „Visserie"
      beziehungsweise „Parafusos e roscas"; ein Wächter über den Wortstamm
      hält alle sechs Sprachen auseinander.
- [x] **Die Werkzeugzeile der Skizze verlangt mit Stylesheet 1007 Bildpunkte —
      Schritt eins gebaut am 23.08.2026 (`bd4fbce`): 1007 → 881.**
      `measure_field` stand dauerhaft grau da und belegte ein Sechstel der
      Zeile; es erscheint jetzt nur, solange gezeichnet wird. Die Grenze ist
      **gesetzt** und nicht behauptet — 900 Bildpunkte, dieselbe Zahl wie die
      Bedingungszeile desselben Bereichs, und sie lebt in
      `test_sketch_editor.py`, weil sie ein gebautes Fenster **mit Thema**
      braucht.

      **Ein bestehender Test hat den Umbau selbst eingefordert, und das ist
      der schönere Teil.** `test_the_tool_row_is_the_one_that_needs_the_width`
      war grün, *solange* die Zeile zu breit war, und trug seine Anweisung an
      die Zukunft im Fehlertext: „Der Bereich passt jetzt auf einen 1024er
      Schirm — schön, und dann gehört die Zahl hier nachgezogen." **Er wurde
      rot, weil der Punkt behoben war.** Umgebaut zum Wächter des behobenen
      Zustands, der neu geschriebene Test dafür wieder gestrichen: zwei Tests
      zum selben Thema wären eine Gelegenheit auseinanderzulaufen.

      Das war die dritte Korrektur an derselben Rechnung, und diesmal ging sie
      zugunsten der Sache aus: **Der Test wusste mehr über den Punkt als das
      Register.**

      Der ursprüngliche Befund, weil seine Messung weiter gilt:

- [x] **Die Werkzeugzeile der Skizze verlangt mit Stylesheet 1007 Bildpunkte —
      gelöst am 23.08.2026** (`bd4fbce` und `8f11279`, 3d-druck-b8).

      **Die Entscheidung, die der Punkt verlangte, ist gefallen: keine der drei
      genannten.** Statt etwas aus der Zeile zu streichen, wandert das Maß beim
      Zeichnen an den **Zeiger** — wie in Fusion. Damit ist das Eintippen der
      Normalweg und nicht mehr eine Funktion, die man kennen muss.

          HEAD, ohne angefangenes Element    881 Bildpunkte
          HEAD, beim Zeichnen              1007
          jetzt, in beiden Lagen            881

      **Schritt eins allein trug nicht:** Er blendete das Feld aus, solange nichts
      gezeichnet wird — beim ersten Klick sprang die Zeile auf 1007 zurück. Erst
      Schritt zwei hält die Grenze in **beiden** Lagen.

      Ursprünglich:
      `test_the_constraint_buttons_stay_readable_on_a_laptop` fordert 900 und
      ist trotzdem grün — weil er allein läuft, und dann steht kein Thema. Läuft
      `test_ui.py` im selben Prozess davor, sind die achtzehn Knöpfe der Zeile
      37 statt 28 Punkte breit, und die Summe reicht über einen 1024er Schirm
      hinaus. Der Fund ist älter als der Bildlauf vom 20.08. und hat nichts mit
      ihm zu tun; sichtbar wurde er, weil die Suite an diesem Tag zweimal am
      Stück lief statt je Datei. Zu entscheiden ist, **was** aus der Zeile
      verschwindet — die zweite Zahl, die Grundformen oder ein Kürzel-Menü —,
      und der Test sollte danach sein Thema selbst setzen, sonst misst er
      weiterhin etwas, das niemand sieht.

---

## Die Bedienung von Beispielen bis Skizze (20.08.2026, dritte Runde)

Auftrag: die Beispielprojekte durchsehen, Text aufbringen und ein Stück aus
einer Fläche ausschneiden — alles über die Oberfläche, mit Blick auf
Einfachheit für den Kunden. Die Skripte und Messungen liegen in
`.claude/.state/durchsicht-2026-08-20b/`.

**Alle neun Beispiele öffnen und rechnen** (1,5–3,8 s). Die zwei, die mit
Warnungen begrüßten, tun es nicht mehr — dahinter standen zwei echte Fehler,
siehe unten.

### Behoben — jeder mit Test und Gegenprobe gegen HEAD

- [x] **Sechs Öffnungen, sechs Mal dieselbe Frage nach der Sicherung**
      (`4e7531b`). Drei Fehler in einer Kette: `closeEvent` sicherte, *nachdem*
      der Nutzer *Verwerfen* geklickt hatte; die abgelehnte Sicherung blieb
      liegen und war weiter neuer als die Datei; und wer sie annahm, arbeitete
      danach in `…p3d.autosave` weiter, während seine eigentliche Datei
      unberührt blieb. Nachher: null Fragen.
- [x] **Die Tasche schnitt daneben, und niemand sagte etwas** (`ee2e9a1`). Vier
      Fälle gemessen, in denen `sketch_pocket` das Volumen unverändert lässt —
      Oberkante unter dem Körper, Ort daneben —, und alle vier stumm.
      `boolean.without_effect` verlangt jetzt nur noch ein Volumen und gilt
      damit auch im exakten Kern.
- [x] **Ob die Fläche zu ist, stand nirgends** (`8079a15`). Die Zeile sagt es ab
      dem ersten Strich („Noch offen · 4 Freiheitsgrade sind noch frei").
      Verschieben gab es gar nicht — nur Punkt für Punkt; `edit.move` schiebt
      die Auswahl, ab Qts Ziehschwelle. Löschen lag allein auf Entf und steht
      jetzt im Kontextmenü.
- [x] **Sieben Werkzeuge hingen an einem Haken, den niemand sah** (`3fdfe3f`).
      Der Umschalter „Exakter Körper" lag unter „Weitere Einstellungen",
      zugeklappt; sein Hinweis nannte STEP und Verrundungen, nicht die Tasche.
- [x] **Ein Quader blieb ein Netz, weil der Haken nur beim Anlegen dastand**
      (`a342e81`). `History.change_kernel` stellt einen Schritt auf seinen
      Zwilling um, und der Dialog im Verlauf trägt denselben Haken.
- [x] **Zwei Beispiele begrüßten mit Warnungen, und beide hatten recht**
      (`b5bd8d3`). Der Deckelkragen bekam das doppelte Spiel (`clearance`
      radial statt diametral, plus eine feste Zugabe von 0,2 mm gegen Regel 7);
      und „Weg 3" zeigte zwei Warnungen, die drei Schritte später behoben waren
      — `SETTLED_BY` streicht sie.

### Offen

- [x] **Der exakte Zweig überlebt keine Mesh-Operation — die Bohrung ist
      gebaut, und das Kriterium für den Rest steht (23.08.2026).**
      `drill_brep_hole` schneidet im exakten Kern, und der Zweig hält:

          exakter Quader -> Bohrung -> Verrundung -> STEP-Export
          Art danach     brep       Volumen 23365,8       35348 Bytes

      Die Kennzahlen gehen gegen die geschlossene Formel und nicht gegen einen
      Vorlauf: Ein Zylinderschnitt hat eine, und der exakte Kern trifft sie auf
      neun Stellen (`rel=1e-9`) — durchgehend, als Sackloch und quer durch den
      Körper. Ein Netz läge um ein knappes Promille daneben, weil die Bohrung
      dort ein Vieleck mit `BORE_SECTIONS` Seiten ist.

      **Die Bohrung war die richtige erste Wahl, und das Kriterium sagt auch,
      wo Schluss ist.** Der Punkt nannte richtig, dass „senken" und
      „verschließen" danach vor derselben Frage stehen. Die Antwort ist **nicht**
      „was im exakten Kern geht" — dann müsste der ganze Katalog zweimal gebaut
      werden, und beide Fassungen wären die halb gepflegten. Sie lautet:

      > Ein Zwilling entsteht dort, wo der Zweig ohne ihn **endet** — nicht
      > dort, wo er möglich wäre.

      Danach ist die Bohrung der erste und vorerst einzige Fall: Sie steht am
      Anfang fast jeder Kette. *Senken* und *verschließen* setzen eine Bohrung
      voraus, stehen also nie am Anfang; wer sie exakt braucht, hat den Zweig
      schon. Die Frage stellt sich wieder, wenn jemand sie tatsächlich vermisst.

      **Ein Schema für beide, nicht zwei gleichlautende.** `drill_brep_hole`
      benutzt `DrillParams` — dasselbe Objekt. Daran hängt `change_kernel`: Es
      reicht die Parameter eines gesetzten Schritts an den anderen Kern weiter,
      und wortgleiche Schemata laufen beim nächsten Nachbessern auseinander.
      Der Test dazu prüft `is`, nicht Gleichheit.

      **Und ein Fund über die Bedienung, den kein Mensch gemeldet hat.** Die
      Operation hieß zuerst „Exakt bohren", und `test_theme_and_palette` fiel
      darüber: Wer „bohren" sucht, bekam den exakten Zwilling **vor** der
      gewöhnlichen Bohrung, weil sein Titel das Wort wörtlich trägt und der
      andere nur über den Wortstamm gefunden wird. Der Reihenfolgefehler war
      die Folge; der eigentliche Fehler war ein Stilbruch — die anderen
      Zwillinge heißen „Exakt**en** Quader anlegen", erst die Sache, dann das
      Beiwort. Sie heißt jetzt „Exakte Bohrung setzen". *Ein Test über die
      Oberfläche hat damit eine Benennungsregel durchgesetzt, die nirgends
      aufgeschrieben ist.*

      **Was dabei nebenbei auffiel und behoben ist:** Die Website nannte an
      zwölf Stellen in sechs Sprachen „86 Operationen". Eine neue Operation
      macht daraus 87 — auf einer Kundenseite, im FAQ und im Zahlenkasten. Der
      Test `test_website.py` fängt es, und das ist der Grund, aus dem er
      existiert.

      Ursprünglich stand hier: Wer einen exakten Quader anlegt und eine
      Bohrung setzt, hat danach ein Netz — die
      Auswertung sagt es (`evaluate.exact_became_mesh`), und der Hinweis am
      gesperrten Werkzeug nennt seit `a342e81` den Schritt beim Namen. Aber der
      Ausweg bleibt mühsam: die Schritte ab dort zurücknehmen, die exakte
      Operation anwenden, den Rest neu setzen. Für „Quader mit Bohrung **und**
      Tasche" gibt es keinen bequemen Weg. Zu entscheiden ist, ob `drill_hole`
      einen exakten Zwilling bekommt — im B-Rep-Kern ist eine Bohrung ein
      Zylinderschnitt, und die anderen Bohrungs-Ops (senken, verschließen)
      stünden danach vor derselben Frage. §25 legt für die Bohrungen keinen
      Kern fest; §30.1 tut es nur für die Skizzen-Ops.

- [x] **Benannte Merkmale überstanden keine Boolesche Operation — und damit
      zerbrach die Passung.** Gemessen am eigenen Vorzeigebeispiel: „Dose mit
      Deckel" öffnen, `label_text` auf die Dose anwenden, und der Prüfbericht
      meldet `fit.missing_feature` als **Fehler**. Der Deckel-Ablauf benennt
      `lid_cavity` und `lid_collar` (§14, sie tragen `provenance="generated"`);
      `label_text` gibt `features={}` zurück, und `_with_features` sucht die
      generierten nur in der **Ausgabe** der Operation — in der Eingabe stehen
      sie noch, werden dort aber ausdrücklich aussortiert
      (`provenance != "generated"`). Vierzehn Operationen geben `features={}`
      zurück; es ist also das Muster und kein Ausreißer, und `label_text` ist
      nur der Fall, an dem es weh tut.

      Der Fix liegt an **einer** Stelle (`_with_features` rettet die
      generierten aus `previous`, wenn die Operation keine mitgibt), aber er
      braucht eine Entscheidung: Wann ist ein benanntes Merkmal wirklich fort?
      Bei `split_pinned` bekämen sonst beide Hälften alle Merkmale der
      Eingabe. `_outside()` filtert bereits nach Hüllquader und wäre der
      Ansatz. Der Satz im Bericht nennt seitdem wenigstens den Grund und
      einen Weg — zurücknehmen und vor der Passung ausführen.

      **Gebaut in `b76df19`, und die geforderte Entscheidung ist darin
      ausgeführt.** `_with_features` nimmt erzeugte Merkmale seither aus
      `previous` mit, statt sie aus der Ausgabe zu lesen; die Stellen mit
      `features={}` gibt es weiter — fünfzehn, zwölf unter `geom/` und je eine
      in `brep/ops.py`, `scene/ops.py`, `sketch/ops.py` —, nur sind sie
      folgenlos geworden. Die Frage „wann ist ein benanntes Merkmal wirklich
      fort" steht als Dreiteilung im Code: Ist die Art **erkennbar**
      (`DETECTABLE_KINDS`), wird das Merkmal wie ein erkanntes zugeordnet und
      fällt heraus, wenn es wirklich weg ist — **mit Befund**, nicht lautlos.
      Ist sie es nicht (Gewinde), reist es ungeprüft mit, weil es geprüft nie
      einen Partner fände. Gibt eine Operation `features={}` zurück, wird das
      Merkmal mitgenommen. Für jeden der drei Fälle steht ein Test.

      **Nachgewiesen am 22.08.2026 an einer echten Booleschen Differenz** —
      die drei Tests fahren `thicken`, also genau nicht den Fall aus der
      Überschrift. Platte mit erzeugtem `op3.bore_1`, dann
      `trimesh.boolean.difference` mit einer zweiten Bohrung: Das erzeugte
      Merkmal überlebt mit seiner Provenienz, die neu entstandene Bohrung wird
      als erkanntes Merkmal daneben geführt, keine Befunde. Gemessen von
      3d-druck-3a.

---

## Die Nutfeder, und zwei Fehler auf dem Weg dorthin (20.08.2026)

Der Durchgang oben hatte `profile_slot` als „Vorarbeit für einen Baustein, den
es nicht gibt" notiert und den Punkt dann selbst zurückgenommen: §24.2 verlangt
die Aluprofil-Nutmaße als *Nachschlagewert*, und als solcher waren sie
erreichbar. Beides stimmt und beides zusammen war die halbe Auskunft — man
konnte die Maße nachschlagen und nicht verbauen. Jetzt gibt es den Baustein.

**Was er ist, war eine Entscheidung und keine Herleitung.** „Profilnut" lässt
drei Bauarten offen: eine Feder am eigenen Teil, ein Nutenstein als eigener
Körper, oder eine Rinne, in der das ganze Profil sitzt. Gewählt ist die erste.
Sie nutzt genau die Maße, die die Tabelle beschreibt — Nutbreite für den Hals,
Kerndurchmesser für den Kopf —, und sie ist die Bauart, mit der ein *in Solidon
konstruiertes* Teil an eine Schiene kommt. Die Rinne hätte die Außenmaße
gebraucht, die dort nicht als Zahlen stehen; der Nutenstein wäre ein gedrucktes
Gewinde in einer Größe, in der es wenig trägt, neben einem Stahlteil für wenige
Cent.

**Zwei Maße kamen in die Tabelle, und sie sind die unsicheren.** Nutbreite und
Kerndurchmesser standen seit der Erstbestückung da; eine Feder braucht dazu die
**Stegdicke** (wie lang der Hals sein muss) und die **Kammertiefe** (wie hoch
der Kopf werden darf). Beides sind Eigenschaften des gekauften Profils und keine
Konstruktionsentscheidung, also gehören sie in die Tabelle und nicht als Vorgabe
an einen Parameter. Eingetragen nach dem Verfahren, das der Kopf von
`standards.toml` selbst festlegt — der gebräuchlichste Wert, die Streuung in
`note` —, und die Streuung ist hier größer als bei den beiden alten: kein
Katalog führt diese zwei, jeder zeichnet sie anders. Die Tabelle steht damit auf
Version 2; kein bestehender Wert hat sich geändert.

**Das Spiel kürzte sich in der Gesamttiefe weg.** Der erste Wurf rechnete den
Hals als `lip + play` und den Kopf als `depth - play` — beides für sich
richtig gedacht, zusammen null. Die Feder war exakt so hoch wie die Nut tief und
stieß mit **null Luft** auf dem Nutgrund auf; ein gedruckter Kopf klemmt so,
bevor er am Steg trägt, und tragen ist seine ganze Aufgabe. Gefunden hat es
nicht die Suite, sondern eine Tabelle über alle drei Größen und drei Spielwerte,
ausgedruckt und angesehen. Der Kopf zieht das Spiel jetzt zweimal ab, und
`test_the_tongue_leaves_air_in_the_slot_it_is_made_for` prüft in beiden
Richtungen gegen die Tabelle: in der Breite gegen den Kerndurchmesser, in der
Tiefe gegen Steg plus Kammer, und übrig bleiben muss genau das Spiel. Das ist,
was `bausteine.md` mit „eine Passung wird an der Differenz gemessen" meint.

**Die entartete Fläche lag mitten im Bereich, nicht an seinem Ende.** Genau bei
`taper == length / 2` fällt die Schulter des Umrisses auf null, und damit fallen
an jedem Ende zwei Ecken aufeinander: bei Länge 6 und Schräge 3 kam ein Körper
aus **fünf** Teilen heraus, der nicht wasserdicht war. Bei Schräge 2, 4 und 6
derselben Länge ging es gut.

Und das ist der eigentliche Fund: **der Bereichstest aus §24.3 hätte das nie
gesehen.** Er nimmt Minimum, Maximum und Vorgabe jedes Parameters, und diese
Stelle ist keines der drei. Aufgefallen ist sie erst an der *Gegenprobe* — die
Kappung im Baustein herauszunehmen ließ alle Tests grün, und genau das war das
Signal: Wer eine Absicherung baut, deren Wegfall nichts rot macht, hat entweder
eine unnötige Absicherung oder einen ungeprüften Fall. Hier war es das Zweite.
`shapes.tapered_bar` fängt den Fall jetzt selbst ab, wie `wedge` es für seinen
tut, und `test_a_tapered_bar_holds_at_every_taper_not_just_at_the_corners`
fährt in Zehntelschritten statt über Ecken.

Die Kappung im Baustein bleibt, aber als das, was sie ist: eine Entscheidung
über die Konstruktion. Eine Schräge über ein Drittel der Länge lässt keinen
tragenden Mittelteil übrig, und geprüft wird das am Querschnitt in der Mitte —
nicht am Volumen, das fiele auch, wenn die Schräge die Mitte auffräße.

**Was nicht nötig war.** Der Bauplan bleibt unverändert: Die Erstbestückung in
§24.1 ist ein historischer Satz von dreizehn, und der vierzehnte
(`snap_connector`, 14.08.) steht dort auch nicht — §24.2 nennt die Nutmaße
ohnehin. `LIBRARY_VERSION` bleibt auf 3, weil beide Vergleichsfunktionen nur
*benutzte* Bausteine melden und ein neuer in keinem alten Projekt steckt. Der
Zählwächter in `test_parts.py` ging von 14 auf 15, mit dem Anlass daneben — er
ist dafür da, dass das auffällt.

Dazu, ohne eigene Arbeit: Vorschaubild, `to_scad`, Menüeintrag, Handbuchseite,
Werkzeug für den Agenten und Kommandozeilenbefehl. Ein Registereintrag, und
jede Oberfläche zieht nach (Leitprinzip 3).

### Was dabei auffiel und liegen bleibt

- [ ] **Stegdicke und Kammertiefe sind an keinem echten Profil gemessen.** Sie
      stehen als gebräuchlichste Katalogwerte in der Tabelle — 1,8 und 4,3 für
      Nut 6, 2,0 und 5,5 für Nut 8 — und `note` nennt die Spanne, die die
      Hersteller aufmachen (Steg 1,8–2,2, Kammer 4,2–6,0). Innerhalb dieser
      Spanne liegt mehr als das Spiel, mit dem gerechnet wird: Wer eine Feder
      druckt, die klemmt oder wackelt, ändert zuerst diese zwei Zahlen und nicht
      das Spiel. Zwei Messungen mit dem Messschieber an einer 2020er und einer
      3030er Schiene würden den Punkt schließen — bis dahin ist die Feder gut
      gerechnet und nicht nachgemessen.

## Der Durchgang durch die offenen Punkte, und ein Review über ihn (20.08.2026)

Fünf Punkte zu, und keiner davon war eine Entscheidung — genau darin lag die
Auswahl. Von den vierundzwanzig hängen elf an etwas außerhalb des Codes
(CI-Dienst, Apple-Zertifikat, DMARC-Eintrag, `support@`-Postfach, Geld für zwei
Agenten-Suite-Läufe) oder sind ausdrücklich keine Entwicklungsaufgabe; sechs
warten auf eine Entscheidung, die niemand anders treffen kann als der, dem die
Anwendung gehört. Die fünf hier waren Arbeit.

### Was dabei über das Vorgehen zu lernen war

**Vier Wächter haben gemeldet, und alle vier zu Recht.** Der Baustein löste sie
aus: der Zählwächter der Bibliothek (14 → 15), „jede Operation hat einen Test",
die Umfangszeile der Pressemitteilung und die Zahlen der Website in sechs
Sprachen. Keiner war Ballast, jeder hat auf etwas gezeigt, das wirklich
nachzuziehen war — 85 Operationen sind 86, 17 Bausteine sind 18, an 27 Stellen
plus Statistikblöcken, Anschreiben und den erzeugten Handbuchseiten.

**Die Gegenprobe hat in diesem Durchgang zweimal mehr gefunden als der Test.**
Beim ersten Mal war es die entartete Fläche in `tapered_bar`: Die Kappung
herauszunehmen ließ alles grün, und das war das Signal — wer eine Absicherung
baut, deren Wegfall nichts rot macht, hat eine unnötige Absicherung oder einen
ungeprüften Fall. Beim zweiten Mal war es der hohle Wächter für die
Katalognamen, der sechsmal die deutschen Namen maß. Die Regel dazu steht in
`.claude/rules/tests.md` und hat sich wieder bezahlt.

**Zwei Risiken sind gemessen und nicht durchdacht worden**, und beide hätten
still zurückfallen können:

- `SETTLED_BY` streicht „zu fein für die Merkmalserkennung", sobald eine
  Dezimierung dahinter steht. Eine Dezimierung, die **nicht** unter die Grenze
  bringt, hebt aber nichts auf. Nachgemessen an der ganzen Kette (1,3 Mio. →
  400 000): Der Befund steht weiter da, weil die Auswertung nach jeder
  Operation neu misst und der frische Befund keinen Heiler hinter sich hat.
  Zwei Tests halten beide Seiten.
- `object_names` entsteht in der Ausgabeschleife der Auswertung — und die läuft
  auch bei einem **Cache-Treffer**, was der häufige Fall ist: Jede
  Parameteränderung wertet neu aus, und alles über der geänderten Stelle liegt
  fertig da. Gegenprobe mit einer Zuweisung nur beim echten Rechnen: Der zweite
  Lauf kennt `{}` und der Bericht sagt wieder „obj_1", genau dann, wenn niemand
  mehr hinsieht.

**Und einmal lag der Fund selbst falsch.** „`decimate` zerlegt glatte Körper"
stimmte in der Beobachtung und nicht in der Ursache: Eine saubere Kugel
dezimiert bis auf 2 000 Dreiecke hinunter wasserdicht. Was zerreißt, ist ein
unverschweißtes Netz, und dass „das kantige Gehäuse dieselbe Stufe unversehrt
überstand", war der Hinweis darauf — es war verschweißt, die Vase aus dem
Erzeuger nicht. Wer nach der Glätte gesucht hätte, hätte lange gesucht.

### Der Regelcheck

Gegen die zweiundzwanzig, nur die Regeln, die das Gebiet berühren:

- **Regel 7 und 8** am neuen Baustein: Alle vier Maße kommen aus der Tabelle,
  die Zahlen im Code sind ein Faktor (`2.0 * play`), eine Kappung
  (`length / 3.0`) und Koordinaten. Keine Toleranz als Konstante.
- **Regel 4** vollständig: Registereintrag, Schema, Geometrietest, Texte in
  fünf Katalogen. Vorschaubild, `to_scad`, Menü, Handbuch, Agentenwerkzeug und
  Kommandozeile kommen aus dem einen Eintrag (Leitprinzip 3).
- **Regel 16** greift nicht: `core/generate.py` hat einen Aufrufer, und der ist
  die Oberfläche, nicht die Agentenschicht. Die drei Transaktionen der Kette
  sind Absicht und seit je geprüft; geändert hat sich nur, wann die dritte
  auslöst.
- **§20 auf dem neuen Pfad**: Seit `decimate` erst verschweißt, gibt es zwei
  Wege durch die Funktion, und der Slot-Test fuhr nur den einen — seine Kugel
  kommt aus `trimesh` und ist verschweißt, ein Netz aus einer Datei ist es nie.
  Nachgemessen: 20 480 Slots in zwei Farben gehen hinein, 4 000 in zwei Farben
  kommen heraus. Jetzt mit Test.
- **Regel 21**: Zwei Fragen gestellt statt geraten — welche Bauart der Baustein
  ist, und woher Stegdicke und Kammertiefe kommen.

Kein Verstoß.

### Was liegen bleibt, und warum

- [x] **Die Objektnamen der Beispielprojekte bleiben deutsch — erledigt am
      23.08.2026 in zwei Commits** (`67b0386` Format 9 → 10 samt
      `Operation.translatable`, `94c0ef7` die dreizehn Namen und fünf Kataloge).
      Ein französischer Kunde liest jetzt „Tolérance" und „Épaisseur de paroi"
      im Objektbaum statt „Toleranz" und „Wandstärke".

      **Der Entwurf von unten hat gehalten, und zwar an der entscheidenden
      Stelle:** Der Vermerk sitzt an der Operation, nicht am Wert. Damit steht
      in der Datei und im Op-Hash die Message-ID, aufgelöst wird erst beim
      Lauf — dieselbe Projektdatei hat in jeder Sprache dieselbe Prüfsumme, und
      ein Cache-Treffer überlebt einen Sprachwechsel.

      **Eine Falle kam beim Bauen dazu, die hier nicht stand.** Die
      Auflösung darf nicht *in* die Parameter geschrieben werden, die in den
      Hash gehen: Erst wurde `resolved` verändert und dann gehasht, und damit
      hing der Schlüssel doch wieder an der Sprache. Es braucht zwei Fassungen
      — `resolved` für den Hash, `for_run` für den Lauf. Der Fehler ist leicht
      zu machen und schwer zu sehen, weil er nur beim Sprachwechsel auffällt.

      **Und eine Entscheidung, die weiterreicht als der Punkt:** Übersetzt wird
      gegen eine *Liste* im Quelltext, nicht gegen „jeder Name, der in einem
      Beispiel steht". Ein Beispiel ist eine Datei wie jede andere, und ein
      Name darin könnte auch von einem Nutzer stammen — dann ist er wörtlich
      gemeint (§4.1). Wer einen Namen ergänzt, trägt ihn in die Liste **und**
      in die fünf Kataloge; das Zweite fängt `test_translations.py`, das Erste
      fängt niemand, und darum steht der Satz im Quelltext daneben.

      Der ursprüngliche Text des Punkts, weil seine Analyse richtig war:

      **(Analyse vom 21.08., unverändert)** Die Befürchtung war ein
      `TranslatableText` in `params`, der bis in `operation_hash` reicht. Nachgesehen am 21.08.: Die
      Befürchtung war ein `TranslatableText` in `params`, der bis in
      `operation_hash` reicht. Die trifft nicht zu, weil er dort nicht
      hingehört. `title_translatable` macht es richtig vor: In der Datei steht
      die **Message-ID als Zeichenkette** und daneben ein Vermerk, dass sie eine
      ist. Der Vermerk gehört an `Operation` (ein achtes Feld, etwa
      `translatable: tuple[str, ...]` mit den betroffenen Parameternamen) und
      nicht in `params` — `operation_hash` liest nur `op`, `params`,
      Eingangs-Hashes, Profil, Qualität und Startwert, also bleibt der Schlüssel
      sprachfrei, ohne dass jemand etwas dafür tun muss.

      **Teuer ist `SceneObject.name`.** Es müsste `TranslatableText | str`
      werden, und gemessen lesen **65 Stellen** in Oberfläche, Export und
      Agentenschicht einen Objektnamen direkt: Objektbaum und Kopfzeile,
      Exportdateinamen (`safe_name`), die 3MF-Baugruppe, die Slicer-Übergabe,
      der Steckbrief. Jede davon braucht ein `str()` oder eine Entscheidung —
      und beim Exportdateinamen ist es eine: Heißt die Datei `Halterung.stl`
      oder `Bracket.stl`, je nach eingestellter Sprache? Ein Dateiname, der mit
      der Anzeigesprache wandert, ist dieselbe Sorte Fehler wie ein
      Cache-Schlüssel, der es tut.

      Dazu unverändert: ein Schritt 8 → 9 mit Migration (`carry_over` genügt,
      alte Namen bleiben wörtlich — dieselbe Begründung wie bei
      `title_translatable`), eine Beispieldatei der Version 8, die vierzehn
      gesetzten Namen in `make_examples.py`, siebzig Katalogeinträge und neu
      erzeugte Beispiele.

      Machbar, und die Reihenfolge ist jetzt klar: erst die Entscheidung zum
      Exportdateinamen, dann `SceneObject.name`, dann das Format. Als eigener
      Durchgang, nicht neben anderen Punkten.
## Eine Zahl trägt ihre Bedeutung nicht mit (Nacht zum 23.08.2026)

Vier Sitzungen, zwölf Stunden, und ein Fehler, der in fünf Gestalten auftrat.
Er steht hier nicht als offener Punkt — es gibt nichts zu bauen —, sondern
weil er in jeder einzelnen Gestalt richtig aussah.

**Die Fälle, in der Reihenfolge, in der sie aufkamen:**

| was gemessen wurde | die Deutung | was wirklich war |
|---|---|---|
| „Grundformen hat vier Zeilen" | *Erzeugen* kann flach werden | die Zahl **einer** Kategorie; die Gruppe hat 18 |
| „achtzehn Knöpfe" | ein Überlaufknopf spart Platz | 15 Knöpfe **und 3 Felder**; die Felder kosten das Doppelte |
| `MAX_TOOLS = 8` | „die Hausgrenze steht schon" | sie gilt einer anderen Werkzeugzeile |
| 681 ms gegen 12,9 s kalt | „merkt kein Kunde" | gegen §31 sind es 23 % statt 5 % |
| `test_ui` reißt 5/5 neben einem Torlauf | Fremdlast | unter Schloss ebenfalls 5/5 |
| ZIP-Stempel wandern | das ist die Ursache | es war **eine** von dreien |
| „Merge failed" | also ist nichts passiert | HEAD bewegt, Dateien geschrieben, Autostash weg |
| 19 Module nacheinander importiert | eines zieht trimesh | die Messung lief in Reihenfolge; je frischer Lauf: 19 von 19 |

**Keine dieser Zahlen war falsch gerechnet.** Jede stimmte. Was fehlte, war
jeweils dasselbe: der Bezug, über den sie eine Aussage macht.

**Drei Fragen, die in dieser Nacht jeden der Fälle gefangen hätten** — sie
kosten Minuten und haben mehrfach Stunden gespart:

1. **Worüber macht diese Zahl eine Aussage?** „Vier Zeilen" — wovon? „Achtzehn
   Knöpfe" — sind es Knöpfe? 681 ms — von wie viel? Der Fehler sitzt nie in der
   Zahl, sondern im Nenner.
2. **Was wäre eine Erklärung, die dasselbe Ergebnis erzeugt und trotzdem falsch
   ist?** Diese Frage hat den Reihenfolge-Fehler beim Importieren gefangen, und
   sie fängt jeden Test, dessen Name mehr verspricht als seine Zusicherung
   (`st_size > 0`, `writes_the_same_bytes`).
3. **Habe ich mit demselben Werkzeug gemessen, das auch entscheidet?** Wer
   Doppelungen mit derselben Zuordnung zählt, die sie filtert, sieht keine.
   Eine Ebene tiefer messen — `cost()` statt `match()` — zeigt, was die
   Optimierung verworfen hat.

**Und eine Beobachtung über die Beteiligten, die mehr wert ist als die drei
Fragen:** Von den acht Fällen hat in **sechs** derjenige den Fehler gefunden,
der die Messung gemacht hatte — nachträglich, ohne dass jemand nachgefragt
hätte. Zweimal fand ihn ein anderer. Das Verfahren, das trägt, ist also nicht
gegenseitige Kontrolle, sondern die Gewohnheit, die eigene Messung noch einmal
gegen ihre Deutung zu halten, **bevor** man sie weitergibt.

## Vier Wege von Hand, während die Suite grün war (23.08.2026)

Vor dem Release für 0.1.3 hat 3d-druck-b8 die vier Wege aus §2.2 **bedient**
statt getestet — echte Qt-Plattform, kein Offscreen, als hätte sie Solidon
gerade heruntergeladen. Parallel dazu meldete die Suite 5268 bestandene Tests.

**Drei Wege sind gefahren, der vierte nicht — und der Unterschied ist erst
aufgefallen, als Robert nachfragte.** Weg 1 kommt ohne Handbuch bis zur STL,
Weg 2 bis zum Körper im Verlauf, Weg 4 bis zur Pinselleiste. Der Abschluss
— Druckeinstellungen und Slicer-Übergabe — ist sauber.

**Weg 3 stand hier zuerst als „ehrlich ohne KI“ und damit als geprüft.**
Tatsächlich waren nur die **Vorbedingungen** gemessen: Chat da, Dienste-Status
ehrlich, Generierungsdialog vorhanden. **Es wurde nie ein Modell erzeugt.**

**Die Rechnung dahinter ist die eigentliche Lehre, und sie gilt für jede
Weitergabe:**

> Die Meldung war die Quelle, die Weitergabe hat sie fester gemacht, und
> niemand hätte je nachgesehen. „Weg 3 gefahren“ wurde zu „drei von
> vier tragen“ wurde zu einer Tatsache. **Ein zu großzügiger Bericht ist kein
> Fehler, den man später korrigiert — er wird auf dem Weg fester.**

Gefunden hat es keine der vier Sitzungen, sondern Robert, weil er wusste, dass
ComfyUI in der Zwischenzeit nichts erzeugt hatte.

**Und die Form des Fehlers ist dieselbe wie zweimal daneben**, nur an der
schwersten Stelle: `if b.text()` maß, was **existiert**, statt was zu sehen
ist; `arrange.below_bed` wurde im Prüfbericht gemessen und über den Export
behauptet; hier wurden die Vorbedingungen gemessen und der Weg behauptet.
**Die ersten beiden fand die Messende an fremdem Code, weil sie dort gesucht
hat. Beim eigenen Bericht hat sie nicht gesucht — sie wusste ja, was sie getan
hatte.** Das ist der Unterschied zwischen prüfen und erinnern.

**Und trotzdem sind vier Fehler herausgekommen, die kein Test gesehen hat.**
Das ist die eigentliche Aussage des Abschnitts:

    Ergebnis-Cache fiel bei jedem konstruierten Projekt aus   b46b289, behoben
    Eine Warnung im Protokoll log                             6bf84ff, behoben
    overlay.py fasst gelöschte Kinder an (fünf Stellen)        offen, unten

**Der Cache ist der teuerste von den dreien, und er stand seit Tagen in jedem
Protokoll.** Seit Objektnamen aus dem Register kommen, ist `SceneObject.name`
ein `TranslatableText`; `json.dumps` kann den nicht ablegen, und der
`TypeError` landete im `except`-Zweig, der für nicht ablegbare B-Rep-Körper
gedacht ist. Ordner weg, eine Zeile ins Protokoll, fertig:

    could not write cache entry d81bbfa2...: Object of type
    TranslatableText is not JSON serializable

Es traf nicht ein Objekt, sondern den Eintrag der **ganzen** Auswertung —
`objects.json` wird für die Szene geschrieben. Für den Kunden hieß das: Jede
Auswertung jedes konstruierten Projekts rechnet neu. **Nichts war falsch, nur
langsam, und genau darum sah es niemand.**

Abgelegt wird jetzt die Message-ID, nie `str(...)` — und dieser Unterschied ist
der Fund im Fund: Die Übersetzung wechselt mit der Sprache, ein Cache tut das
nicht. Wer `str()` genommen hätte, bekommt nach einem Sprachwechsel den alten
Namen zurück: **ein Fehler, den nur ein warmer Cache zeigt und den darum beim
Entwickeln nie jemand sieht.**

**Ein Zwischenfall beim Testschreiben, der größer ist als der Fix, zu dem er
gehört.** Die ersten beiden Tests zum `discover`-Fix waren grün, **ohne etwas
zu prüfen**: `conftest.py` ersetzt `find_program` für die ganze Suite durch
eine Attrappe (§38, die Suite fragt die Maschine nicht), und eine Attrappe
protokolliert nie. Eine Zusicherung auf eine **ausbleibende** Warnung ist dort
immer erfüllt. Das Original steht seither als `unpatched_find_program`
daneben.

> Wer auf das **Ausbleiben** von etwas prüft, prüft am leichtesten nichts.
> Eine Gegenprobe fängt es in zehn Sekunden: Fix zurücknehmen, Test muss rot
> werden.

**Die Bilanz des Messenden, und sie gehört zum Bild:** b8 hat an diesem
Vormittag **vier** eigene Fehlbefunde vor dem Melden abgefangen und einen
nicht — `sculpt_push` gibt es nicht (die Ops heißen `sculpt_strokes` und
`pose_armature`); `install.statuses()` meldete einmalig `present=False` und
dreimal danach `True`; zwei Knöpfe hießen scheinbar gleich, weil ihr Filter
`if b.text()` erhob, **was existiert, statt was zu sehen ist**; und
`arrange.below_bed` ist beim Export längst eine Warnung statt eines Hinweises
(`_severity_for(about_to_write=True)`), was sie aus dem Prüfbericht
geschlossen und nicht am Export gemessen hatte.

> **Wer viel misst, erzeugt viel Rohmaterial, und ein Teil davon ist Schrott.**
> Der Wert liegt darin, ihn vor dem Melden auszusortieren — nicht darin,
> keinen zu erzeugen.

### Was ein Belegslauf leistet, wenn man ihn ernst nimmt

Der Lauf vor 0.1.3 hat **zwei** Fehler gefangen, und beide hätten ein Paket
erreicht. Keiner davon stand in einem Test, der vorher rot war.

**Erstens: Der Baumzustand gehört mit belegt.** Vor dem Lauf stand eine sieben
Stunden alte Arbeitskopie von `tests/test_way_four.py` im Baum — Rest eines
gescheiterten Merges (Autostash nicht zurückgespielt). Sie nahm `place_on_bed`
aus dem Test und setzte den Sculpt-Bezug wieder auf `ops[-1]`, also genau das,
wogegen `abce5f3` gebaut worden war.

> Ohne den Handgriff hätten wir eine 0.1.3 gebaut, in der ein Test still auf den
> Stand von 01:18 zurückgefallen wäre — **und gemerkt hätte es niemand: Der
> Test wäre grün gewesen.**

Das ist der Fall, gegen den kein Test hilft, weil der Test selbst das Opfer ist.
`git diff HEAD --name-only` vor dem Lauf kostet eine Sekunde.

**Zweitens: `test_packaging.py` schlug genau in dem Lauf an, für den es gebaut
wurde.** Drei erzeugte Dateien trugen noch 0.1.2, während `branding.py` schon
0.1.3 sagte — ein Paket, das außen neu aussieht und innen alt ist. Im Probelauf
zwei Stunden vorher war die Datei grün, weil die Version da noch nicht erhöht
war.

> Das ist kein Ärgernis, das ist ein Treffer.

Behoben wurde die Ursache: `bump_version.py` **ruft** die beiden
`--files`-Werkzeuge jetzt selbst (`DERIVED`), statt sie im Ausgabetext zu
nennen. Die Notiz zu dem Werkzeug sagte „beide Stellen“, und es waren drei;
ein Hinweis hätte die vierte beim nächsten Zuwachs genauso verpasst.

### Offen aus diesem Durchgang

- [x] **`overlay.py` fasst Körper an, die es nicht mehr gibt — fünf Stellen,
      nicht eine.** Aus 33s Belegs-Probelauf, nachgemessen von b8:

      **Gebaut am 23.08.2026** (`ddb27e6`, `02914d5`, 3d-druck-b8): Alle fünf
      `findChildren`-Stellen filtern auf lebende Objekte.

          app/ui/overlay.py:346
          if isinstance(child, RoomTaker) and child.isVisibleTo(zone)
          RuntimeError: Internal C++ object (ObjectTree) already deleted.

      `findChildren` steht an **276, 294, 345, 438 und 655**, und jede Stelle
      fasst die Kinder sofort an. **Keine hat eine `isValid`-Wache** — die Datei
      kennt `shiboken6` gar nicht. Die Aufräum-Fixture macht es für die
      Top-Level-Widgets vorbildlich; für die Kinder macht es niemand.

      **Der Kundenpfad ist derselbe:** `closeEvent` ruft `wait_for_workers`,
      das läuft über `session.wait_for_idle`, und dort steht `processEvents` —
      dieselbe Schleife, in der der `eventFilter` auf halb abgebauten Kindern
      feuert.

      **Der Schaden, ehrlich gerechnet:** Eine Ausnahme in einem `eventFilter`
      bringt die Anwendung **nicht** um. PySide meldet
      „Error calling Python override“ auf stderr und macht weiter; der Kunde
      ohne Terminal sieht nichts. Was bleibt, ist ein ERROR im Teardown, der
      einen Belegslauf verunsichert.

      **Der nächste Schritt ist benannt:** eine Hilfsfunktion in `overlay.py`
      (`lebende(zone, typ)`), die `findChildren` filtert, und fünf
      Aufrufstellen darauf umgestellt — reine Absicherung, bei gültigen
      Objekten ändert sich nichts. Dazu ein Test, der ein Kind löscht und die
      Rechnung trotzdem durchlaufen lässt.

      **Vor dem Release ausdrücklich nicht gemacht**, und der Grund ist
      messbar: Der Fix kostet drei `test_ui.py`-Läufe unter dem Schloss — und
      genau diese Datei ist die, bei der drei Läufe **drei verschiedene
      Ausgänge** haben. Ein Fix, dessen Wirkung man an seiner eigenen Datei
      nicht ablesen kann, ist der schlechteste Kandidat für den Tag vor einem
      Release.

- [ ] **Fünf Fensterdateien reißen **vor** ihrer Zusammenfassung — und einzeln
      laufen sie durch.** Die Signatur, die nach dem Abbau-Absturz übrig bleibt,
      und sie ist eine andere. Torlauf vom 23.08.2026 auf ruhigem Baum
      (`a48d863`), **5057 Tests bestanden, kein einziger roter**:

      ## Sortiert am 23.08.2026 an **24 Absturzstapeln**

      3d-druck-33 hat die Protokolle eines Tages ausgewertet statt der
      Erinnerung. Die Codes:

          19x  access violation (0xC0000005)
          16x  0xc0000374 (Heap)
           1x  Fatal Python error: Aborted

      Und die Stellen im **eigenen** Code, absteigend:

          11x  app/ui/session.py:1478  wait_for_idle   <- processEvents()
          10x  app/ui/session.py:1460  wait_for_idle
           9x  app/ui/session.py:112   _EvaluationWorker.__init__
           9x  app/ui/session.py:1065  evaluate_async  <- erzeugt den Arbeiter
           8x  app/ui/leash.py:173     run

      **Das ist keine Streuung, sondern eine Konstellation:** Der Hauptthread
      steht in `wait_for_idle` und ruft dort `processEvents()`, während ein
      `_EvaluationWorker` in `run_evaluation` rechnet. Zwei Seiten derselben
      Zange, in fast jedem Stapel.

      > **Signatur B: `processEvents()` läuft gegen einen rechnenden Arbeiter.**
      > Codes `0xC0000005`/`0xC0000374`, immer **vor** der Zusammenfassung,
      > Stelle wandert, Rate 25 bis 50 Prozent je Fensterdatei.
      > **Belegt an 21 von 24 Stapeln.**

      **Nachtrag vom 24.08.2026: die Zahl der Fenster einer Datei ist ein
      Faktor, und zwar ein schwacher.** Gemessen an `tests/test_selection.py`,
      zehn Läufe je Seite unter dem Schloss, Latte vorher gesetzt (ab 4 von 10
      gilt der Beitrag als belegt): **ohne drei zusätzliche Viewport-Instanzen
      0 von 10 gerissen, mit ihnen 2 von 10.** Damit ist er *nicht* belegt, die
      Richtung aber sichtbar; zwei Tests wurden zusammengelegt, die denselben
      Körper doppelt aufbauten. Die Stapel stützen Signatur B: `Session.__init__`
      → `evaluate_async` → `_on_thread_done` → `wait_for_idle`, einmal
      „Garbage-collecting" als ganzer Stapel, jedes Mal `0xc0000374` und **kein
      fehlgeschlagener Test**.

      **Und die Methode ist billiger als hier steht.** „Zehn Läufe je Seite
      (~40 min)" gilt für `test_ui.py`; an einer Datei, die fünf Sekunden
      läuft, sind zehn Läufe **eine Minute**. Wer die große Frage angeht, holt
      sich den Vergleichsarm dort, statt ihn zu überspringen.

      **Vier Registerpunkte sind hierin aufgegangen** — sie beschrieben
      dieselbe Sache aus vier Richtungen: *Ein Absturz vor der Schlusszeile*
      (dieselbe Formulierung), *Der Absturz beim Aufräumen* (`session.py:110`
      liegt zwei Zeilen neben der Stelle aus neun Stapeln), *`test_ui.py` reißt
      unzuverlässig* (das ist die **Rate** dazu, keine eigene Ursache) und
      *Ein dritter Absturz in `test_operation_ui.py`*.

      **Abgegrenzt bleiben zwei:** Signatur A (Abbau-Absturz, `0xC0000409`
      **nach** vollständiger Zusammenfassung) ist am 23.08. behoben. Signatur C
      (der Hänger) steht als eigener Punkt — **B stirbt sofort, C stirbt gar
      nicht.**


          test_analysis_ui.py     127   keine Summe, ~33 Tests gelaufen
          test_chat_ui.py         139   keine Summe, ~11 Tests
          test_operation_ui.py    139   keine Summe, ~20 Tests
          test_sculpt_session.py  127   keine Summe, ~28 Tests
          test_ui.py                ?   keine Summe

      **Dieselben vier laufen einzeln sauber durch** (`test_chat_ui` 40 passed,
      `test_analysis_ui` 119, `test_operation_ui` 50, `test_sculpt_session` 31).
      Der Unterschied ist also weder die Datei noch die Aufräum-Fixture — die
      ist gemessen entlastet: A/B im eigenen Arbeitsbaum, nur die
      Fixture-Verzweigung getauscht, **4 von 4 sauber mit der neuen gegen 3 von 4
      mit der alten**.

      **Eine Hypothese ist gemessen und zurückgezogen worden** (3d-druck-33,
      23.08.2026): dass die **Sammelgruppe mit acht Prozessen**, die
      `suite-getrennt.sh` vor den Fensterdateien fährt, einen Zustand
      hinterlässt, den die Fensterprozesse erben.

          ohne Sammelgruppe davor    1 von 4 gerissen
          nach der Sammelgruppe      2 von 4 gerissen

      **Eins gegen zwei bei je vier Läufen ist keine Aussage** — das liegt nach
      der Basisratentabelle in derselben Datei vollständig im Rauschen. Die
      Hypothese ist damit **weder bestätigt noch widerlegt, sondern ungemessen**,
      und das ist ein Unterschied.

      Dazu kommt: `test_analysis_ui` riss in **beiden** Durchgängen, auch ohne
      Sammelgruppe — während dieselbe Datei eine Stunde vorher im A/B sauber
      durchlief (119 passed). Dieselbe Datei, derselbe Arbeitsbaum, zwei
      Ergebnisse.

      **Was gesagt werden kann, und nur das:** Die Risse sind sporadisch mit
      einer Rate zwischen 25 und 50 Prozent je Datei, sie treten **vor** der
      Zusammenfassung auf (anders als der behobene Abbau-Absturz), und der Code
      war beide Male `0xC0000374` (Heap-Beschädigung).

      **Eine belastbare Aussage kostet zehn Läufe je Seite** — rund vierzig
      Minuten auf einer Maschine, die drei andere Sitzungen brauchen. Nicht
      release-kritisch; wer den Punkt aufnimmt, plant die Rechenzeit ein.


      **Dieselbe Datei macht Tests falsch rot, nicht nur Läufe kaputt**
      (24.08.2026, gemessen von formwerk-be). Sieben Läufe von `tests/test_ui.py`
      gegen einen Stand: viermal 258 passed, zweimal Segfault, **einmal 2
      failed** — und die zwei sind einzeln grün und mit `-p no:randomly` in der
      ganzen Datei auch.

      Der Stapel des roten Laufs nennt den Grund: **4378 verschachtelte Frames**
      in `NavigationKeys.eventFilter` (`app/ui/shortcut_schemes.py:131`),
      ausgelöst von `dialog.show()` in `_open_operation_dialog`, als derselbe
      Test zum zweiten Mal `run_operation` ruft und der erste Dialog sich dabei
      schließt. Der `TypeError: eventFilter(QWidgetItem, QEvent)` am Ende ist die
      **Folge** des erschöpften Stapels und keine eigene Ursache — bei dieser
      Tiefe kommt PySide bei der Argumentkonvertierung durcheinander. Ein
      Stapelüberlauf auf der C++-Seite ist zugleich die zwanglose Erklärung für
      die Segfaults derselben Datei.

      Der Filter ist korrekt nur einmal installiert (`_INSTALLED`), es ist also
      **keine** gewachsene Filterkette — genau den früheren Fehler beschreibt
      sein Docstring. Was die Kaskade auslöst, ist offen; `dialog.show()` mit
      einem sich schließenden Vorgänger und dem Fokuswechsel dazwischen ist die
      Spur, nicht die Antwort.

      **Zwei naheliegende Erklärungen sind widerlegt, beide von formwerk-be an
      Minimalbeispielen:** Eine Python-Hülle ohne gelaufenen `__init__` entsteht
      **nicht**, wenn die letzte Python-Referenz fällt — PySide hält die Hülle
      einer Klasse mit Überschreibungen fest, und alle Attribute waren da. Und
      ein wirklich zerstörtes C++-Objekt liefert `RuntimeError: Internal C++
      object already deleted`, **nicht** `AttributeError`; ein AttributeError ist
      also gerade kein Zeichen für ein abgebautes Objekt. Ein `QWidgetItem` als
      `watched` läuft python-seitig anstandslos durch — der TypeError entsteht
      erst im `super()`-Aufruf, also innerhalb unseres Filters, und nicht beim
      Zustellen durch Qt.

      **Ein früherer Nachtrag an dieser Stelle behauptete ein Use-after-free und
      ist zurückgezogen** (eingetragen in `4d473346`, korrigiert am selben Tag).
      Er nannte „Qt übergibt nie ein `QWidgetItem`" als Beleg für einen
      Zeiger auf freigegebenen Speicher. Der erste Halbsatz stimmt, der Schluss
      nicht: Es hat nie jemand ein `QWidgetItem` gesendet. Die Kette ist ein
      Lehrstück über zwei Sitzungen — eine Beobachtung wurde auf dem Weg zur
      Nachricht fester, als sie war, und die empfangende Sitzung trug sie ein,
      weil sie „belegt" hieß.

      Praktische Folge, die keine Untersuchung braucht und von der Ursache
      unabhängig ist: **Ein roter Test in einer Fensterdatei ist erst echt, wenn
      er einzeln rot ist.** Das kostet eine Sekunde und hat am 24.08. in zwei
      Sitzungen je eine halbe Stunde Suche gespart.

      Nicht getan und mit Grund: `_placing` in `overlay.py` als Klassenattribut
      zu deklarieren beseitigte einen der beiden Fehler und verdeckte, was ihn
      auslöst. Ein Pflaster auf einer Ursache, die man nicht kennt, macht die
      nächste Erscheinungsform schwerer zu finden.

      **Zweite Korrektur derselben Kette** (24.08.2026, formwerk-be). Auch die
      Rekursions-Erklärung ist zurückgezogen: ein Zähler im Filter, fünf Läufe,
      **höchste Tiefe 2** — auch in den roten. Die 4378 Frames waren Symptom,
      nicht Ursache. Vorgearbeitet hat eine Gegenmessung von formwerk-20:
      `super().eventFilter()` ruft sich nicht selbst, die Tiefe bleibt bei 1,
      also konnte der Filter die Kaskade nicht erzeugen.

      Was bleibt, ist ein Abzug mit **beiden** Threads: `_PreviewWorker` in
      `copy.deepcopy` (`app/ui/session.py:1284` — `preview_scene` kopiert das
      Dokument tief) gegen den Hauptthread im Speicherbereiniger
      (`session.py:1515` `wait_for_idle` ← `main_window.py:7148` `release` ←
      `tests/conftest.py:255`), Ende in `Fatal Python error: Aborted`. Damit hat
      „Vier Stapel zeigen auf `session.py:1515`" einen Gegenspieler mit
      Zeilennummer: **1284 gegen 1515**.

      A/B: `preview_async` im Hauptthread statt im Arbeiter — drei Läufe
      **identisch** (`22 failed, 236 passed`; die 22 sind der Patch selbst, weil
      diese Tests den Arbeiter erwarten), **null Abbrüche**. Dieselbe Datei mit
      Arbeiter, neun Läufe: sechsmal grün, einmal falsch-rot, zweimal Segfault.
      Deterministisch ohne den Arbeiter, schwankend mit ihm.

      **Grenze der Aussage, und sie steht hier, weil dieselbe Kette schon zwei
      Erklärungen verbraucht hat:** Der Patch nimmt einen Thread weg und ändert
      damit mehr als den Ort der Rechnung — ein Hinweis, kein Beweis. Umgesetzt
      ist nichts; die Vorschau in den Hauptthread zu verlegen wäre eine
      Verhaltensänderung an §18.7.

- [ ] **Signatur C: der Hänger — kein Absturz, sondern Stillstand.** Abgegrenzt
      am 23.08.2026 bei der Sortierung der Absturzfamilie an 24 Stapeln.

      **Der Hauptthread hält den GIL und wartet auf einen Qt-Mutex; ein
      Nebenthread hält den Mutex und will den GIL.** Beide warten, keiner
      stürzt. Dreimal belegt mit verschiedenen Widgets (3d-druck-b8), einmal
      gemessen bei Test 59 mit 250 Sekunden Zeitlimit (3d-druck-33).

      > **Nicht dasselbe wie Signatur B:** B stirbt sofort, C stirbt gar nicht.

      Das ist der Grund, aus dem beide getrennt geführt werden — ein Lauf, der
      **steht**, sieht im Protokoll aus wie einer, der rechnet, und keine
      Absturzsignatur passt darauf. `py-spy dump --pid N --native` ist das
      Werkzeug dafür; die Falle beim Finden der Prozessnummer steht in
      `.claude/rules/tests.md`.

      **Drei Behebungsversuche sind gemessen und widerlegt** (22./23.08.). Was
      fehlt, ist nicht ein weiterer Versuch, sondern eine Messstelle, die eine
      Änderung in wenigen Läufen bewertet statt in zwanzig.

- [x] **Ein Importzyklus in `app/core/scene` — latent, und jede Parallelität
      stolpert darüber.** Gefunden am 23.08.2026 beim Messen der Startzeit:

      > **Die Diagnose unten war falsch, und die drei widerlegten Ansätze waren
      > deshalb folgerichtig wirkungslos.** Es ist kein Zyklus, sondern eine
      > Lock-Inversion, und es war nicht ein Paket, sondern sieben. Was
      > wirklich dahintersteckt, steht im Abschnitt „Ein Deadlock, der keiner
      > war" am Ende dieser Datei. Der Text hier bleibt stehen, weil die
      > **Messungen** darin stimmen — nur ihre Deutung nicht.

      ## Drei Ansätze sind gemessen und widerlegt (23.08.2026)

      **Reproduziert: 5 von 5.** Python erkennt ihn selbst und wirft
      `_DeadlockError("deadlock detected by _ModuleLock('app.core.scene.history')")`.

      **Es sind zwei Module, nicht eines.** `history.py` **und** `evaluate.py`
      importieren beide `from app.core.scene import expressions` — ein Fix an
      einem allein kann darum nie greifen. (Gemessen über den AST aller Module
      unter `scene/`; sonst importiert keines zurück.)

      Was **nicht** hilft, damit es niemand ein zweites Mal versucht:

      - **`import app.core.scene.expressions as expressions`** statt des
        Attributzugriffs — in beiden Modulen. Der Deadlock bleibt: Er hängt am
        **Lock** des Pakets, nicht am Attribut eines halbfertigen Moduls.
      - **Verzögerter Import in der Funktion** statt am Modulkopf. Bleibt
        ebenso — Thread B hält den Lock auf `history`, bevor irgendeine
        Funktion läuft.
      - **`expressions` in `__init__.py` vorziehen**, vor `evaluate` und
        `history`. Bleibt ebenso, aus demselben Grund.

      **Die Gegenprobe zeigt, dass es unser Aufbau ist und kein Python-Verhalten:**

          app.core.scene       _DeadlockError
          app.core.geom        sauber
          app.core.perceive    sauber
          app.core.knowledge   sauber

      Die drei sauberen haben **keinen Rückimport** aus ihrem eigenen Paket. Das
      ist der Unterschied, und damit auch der Weg: **Der Rückimport muss weg**,
      nicht anders geschrieben — `expressions` an einen Ort, der nicht unter
      `scene` liegt, oder die zwei Funktionen dorthin, wo sie gebraucht werden.
      **Das ist ein Umbau und kein Einzeiler**, und er lohnt sich erst, wenn
      jemand Parallelität wirklich braucht.


          app/core/scene/__init__.py:13   from app.core.scene.history import History
          app/core/scene/history.py:30    from app.core.scene import expressions

      Sequenziell löst Python das über die Reihenfolge auf, und niemand merkt
      etwas. Zwei Threads, die gleichzeitig an verschiedenen Stellen einsteigen,
      sehen das halbfertige Modul: **5 von 5 Läufen gescheitert** mit
      `cannot import name 'History' from partially initialized module`.

      > Eine Abhängigkeit, die nur deshalb funktioniert, weil niemand sie
      > **gleichzeitig** benutzt.

      Kein Startzeit-Thema (die Ersparnis dort wären 37 ms), sondern ein
      Struktur-Thema. Wer künftig irgendwo Parallelität einbaut, läuft wieder
      hinein — und sucht dann im eigenen Code.

- [x] **22 von 70 Widget-Klassen bleiben ungeprüft, und die Auswahl ist gegen
      den Kunden gerichtet.** Gemessen am 23.08.2026 (3d-druck-b8): Der
      Lebensdauertest baut jede Klasse und sieht nach, ob sie freigegeben wird.
      **22 lassen sich nicht ohne Argumente bauen** und fallen dabei heraus —
      darunter `OperationDialog`, `PrintSettingsDialog`, `SettingsDialog`,
      `UpdateDialog`, `FirstRunDialog`.

      **Gebaut am 23.08.2026** (`87cfdbc`, 3d-druck-b8): Bauhelfer für alle 22.
      Der Test prüft jetzt **41 Klassen statt 14**, alle grün. Ertrag: vier
      weitere Ringe (`AskDialog`, `ParameterDialog`, `OperationDialog`,
      `PointDialog`) plus `PartCatalog` — geschätzt waren „rund vier“.

      **Der systematische Teil:** Was Argumente braucht, steht meist **mitten in
      einem Arbeitsablauf** — also genau dort, wo ein Leck weh tut. Von den 34
      prüfbaren hielten **sechs** fest.

      Was fehlt, sind Bauhelfer je Klasse. Das ist ein Umbau und kein Abschluss;
      als „erledigt“ getarnt wäre er in einer Woche vergessen. Dazu die zweite
      Zahl aus demselben Nachmittag: Am Ende eines Laufs leben **1705
      Top-Level-Widgets**, zweimal gemessen, exakt dieselbe Zahl — ein
      Fortschrittsmaß, **keine Ursache** (nach 14 Tests waren es achtzig, und
      der Lauf riss trotzdem).

- [x] **Das signierte Lizenz-Manifest ist nicht eingecheckt — gemessen am
      23.08.2026, und es **darf** auch nicht.** Zweimal gebaut, verglichen:

          Dateiprüfsummen   identisch
          signature         verschieden

      **Die Nicht-Reproduzierbarkeit ist eine Sicherheitseigenschaft, kein
      Mangel.** Das Schlüsselpaar ist **je Bau frisch**: Der öffentliche Teil
      wird vor dem Übersetzen in die Kopie von `integrity.py` gesetzt, der
      private nach dem Signieren verworfen und nie abgelegt. Wer das Manifest
      neu schreiben will, muss zuerst den öffentlichen Schlüssel im
      **kompilierten** Modul austauschen.

      **Einchecken würde genau das aufweichen** — und der Diff wäre bei jedem
      Bau ein anderer, ohne dass sich etwas geändert hätte. Der Vorschlag,
      der hier stand, war falsch; er ist zurückgezogen.

      **Was von dem Punkt bleibt, ist gelöst:** `test_packaging.py` fängt ein
      veraltetes Manifest und nennt den Befehl dazu — am 23.08. genau einmal
      geschehen, nachdem eine Grenzdatei sich geändert hatte. **Der Baum zeigt
      es nicht, aber das Tor tut es.**

      Ursprünglich: und darum sieht
      niemand, ob es zum Baum passt.** `tools/build_licence_module.py` schreibt
      nach `packaging/build/`; nach dem Lauf zeigt `git status` **nichts**.

      > Ein Arbeitsergebnis, das `git status` nicht zeigt, existiert für die
      > anderen Sitzungen nicht.

      In der Nacht zum 23.08.2026 haben zwei Sitzungen unabhängig dasselbe
      Manifest gebaut, ohne voneinander zu wissen. Am selben Tag hätte ein
      veraltetes Manifest beinahe ein Paket erzeugt, das **startet und gesperrt
      ist** — gefangen hat es `test_packaging`, nicht der Baum.

      **Zu prüfen wäre, ob die Signatur reproduzierbar ist.** Wenn ja, gehört das
      Manifest eingecheckt: Dann sieht jede Sitzung am Diff, ob es passt. Wenn
      nein, bleibt das Ansagen die einzige Abhilfe. **Gemessen hat das niemand.**

- [x] **Eine Fremdmeldung sagt „Netzwerk“ und meint „Platte voll“.** Beim
      Einrichten von Weg 3 am 23.08.2026 brach der 7,5-GB-Download dreimal ab:

      **Gebaut am 23.08.2026** (`940234d`): `fetch_weights` prüft den freien Platz
      **vor** dem Download (`NEEDED_GIGABYTES`, 9 GB für 7,5 GB Gewichte plus Luft)
      und nennt in der Meldung den freien Platz, den nötigen und den Ort der
      Gewichte — damit einen Handlungsvorschlag statt einer Diagnose. Zwei Tests,
      gegengeprobt.

          RuntimeError: File reconstruction error: Internal Writer Error:
          Background writer channel closed

      **Kein Wort von fehlendem Platz**, und `C:` hatte null Byte frei. Wer die
      Meldung liest, sucht am Netz. Aufgeklärt wurde es nicht durch den Text,
      sondern dadurch, dass der Abbruch **dreimal an derselben Stelle** kam.

      Die Regel „Ein Fehler des fremden Programms wird durchgereicht“
      (`.claude/rules/kern.md`) bleibt richtig — sie hat hier nur eine Lücke:
      **Wo wir mehr wissen als das fremde Programm, gehört das dazu.** Ein Blick
      auf den freien Platz an dieser Ausnahme in `comfy_setup` ist ein Satz und
      erspart die Suche.

      Der Rest hat dabei funktioniert: Der Download lief dreimal von selbst
      wieder an, und `readiness` nannte die vier fehlenden Knoten beim Namen
      (`TripoSGLoader`, `TripoSGImageToMesh`, `TripoSGPostprocess`,
      `TripoSGExportMesh`) statt „ein Knoten fehlt“.

- [ ] **`3D Drucker/` liegt nur auf einer Maschine.** Der Ordner hat ein
      **eigenes** `.git` und **kein Remote** — 458 MB, 83 nicht committete
      Dateien, letzter Commit `5918740`. Die `CLAUDE.md` behauptete bis zum
      23.08.2026 das Gegenteil (*„im Repository: es wird auf drei Maschinen
      gearbeitet“*, korrigiert in `3ce454f`).

      **Kein Entwicklungsthema, sondern ein Datenthema:** Fällt die Platte aus,
      ist die Konstruktionsarbeit an den Druckprojekten weg. Entscheidung von
      Robert, ob ein Remote eingerichtet wird.

- [x] **Der Fenstertitel sagte „Unbenannt“, während der Objektbaum den Namen
      zeigte.** Wer eine STL ablegte, sah oben `Unbenannt* — Solidon3D` und
      darunter `plate_holes`. Sachlich richtig — es gibt noch keine
      Projektdatei —, aber der Kunde hat gerade etwas geöffnet, das einen Namen
      hat.

      **Roberts Entscheidung am 23.08.2026:** „mach den fenstertitel mit dem
      abgeleiteten namen“. Gebaut in `8b4f2a5`.

      Der Titel nennt jetzt, **was offen ist, statt was fehlt**: `plate_holes
      (ungespeichert)` statt `Unbenannt*`. Der Stern bleibt der Datei
      vorbehalten — er heißt „seit dem Speichern geändert“, und wo nie
      gespeichert wurde, hat er nichts zu melden; das steht im Klartext daneben.

      **Zwei Eigenschaften, nicht eine**, und das ist der Teil, der beim
      nächsten Mal Zeit spart: `document_name` gibt den nackten Namen für den
      Dateidialog („Speichern unter…“ schlägt `plate_holes.p3d` vor), `title`
      den Satz für die Titelzeile. Wer beides in eine Eigenschaft legt, bekommt
      irgendwann eine Datei namens `plate_holes (ungespeichert).p3d`.

- [x] **Die deutsche Quelle trennt die Fläche nicht von der Belegung — und das
      ist die Wurzel unter allen Übersetzungsfunden dieses Tages.** Gezählt am
      23.08.2026:

      **Gebaut am 23.08.2026** (`01815fd`, `b880151`, 3d-druck-3a; Website und
      Handbuch `d60b40a`). **21 Schlüssel in 14 Dateien, alle von Hand** — ein
      Skript ging nicht, weil „Platte“ feminin und „Bett“ neutrum ist und in
      einem Satz das Pronomen mitwandert (*„Wie warm die Platte ist. **Sie**
      hält das Teil“* → *„…das Bett ist. **Es** hält das Teil“*).

      **Es waren 21 und nicht 36:** Gezählt worden waren Vorkommen, sortiert
      werden musste nach Bedeutung. Zwei liefen sogar **gegenläufig** —
      Belegung, die „Bett“ sagte. Wer nur ersetzt, macht die schlimmer.

      Die Kataloge kostete es nichts: Schlüssel umbenannt, Wert übernommen.
      **Und eine fünfte Fundstelle war die Festplatte** (*„Liegt die Datei noch
      nicht auf der Platte“*) — ein drittes Wort für dasselbe Zeichen, beinahe
      mit umbenannt.

          Druckbett     10 x        dieselbe Flaeche, zwei Woerter
          Druckplatte   36 x

      Dazu heißt „Platte“ **auch** die Belegung („beginnt eine neue Platte,
      sobald die aktuelle voll ist“). Ein Wort, zwei Dinge — und eine dritte
      Bedeutung als **Bauteil** (*Rückplatte*, *Deckelplatte*), die 3d-druck-3a
      beim Übersetzen gefunden hat und ohne die zehn Bauteilbeschreibungen zu
      Druckbetten geworden wären.

      **Keine Übersetzung kann das auflösen**, und jede Sprache hat es anders
      geraten. Gemessen an beiden lokal installierten Slicern:

          Quelle "bed"    fr  plateau 76:1 plaque    it  piano 42
          Quelle "plate"  fr  plaque  75:28 plateau  it  piatto 59:15

          (ElegooSlicer, Bambu-Abstammung. PrusaSlicer kennt nur ein Wort:
           es hat keine Mehrplatten-Verwaltung.)

      `fr` und `it` sind am 23.08. bereinigt (`258523a`), `en`, `es` und `pt`
      danach. **Offen bleibt die deutsche Seite:** „Druckplatte“ →
      „Druckbett“ wären 36 Stellen, und **jede ändert einen Katalogschlüssel** —
      alle fünf Sprachen fielen auf einmal auf ungebübersetzt zurück. Solange
      die Quelle nicht trennt, sammelt jede Übersetzungsrunde einen Teil davon
      wieder ein.

- [ ] **Die Belegung heißt in `es` und `pt` noch nicht entschieden.** Elegoo
      sagt für `es` `bandeja` (65) gegen `placa` (18); für `pt` steht es
      **69:69**. Das ist eine Wortwahl und keine Messung — bei unentschiedener
      Quelle bleibt der Bestand stehen.

- [x] **Neunundsechzig graue Zeilen in vier Menüs, und keine davon erklärte
      sich.** Gezählt auf der leeren Szene, also genau dort, wo ein Kunde nach
      dem Startbildschirm steht:

      | Menü | bedienbar |
      |---|---|
      | *Objekt* | 0 von 5 |
      | *Ändern* | 0 von 34 |
      | *Bausteine* | 0 von 20 |
      | *Vorbereiten* | 0 von 10 |

      **Robert:** „wenn man kein 3d modell ausgewählt hat bringen menüs wie
      bohrung anlegen nichts, hier ausblenden“, und auf die Rückfrage:
      „ausblenden wenn es nicht sinnvoll ist“. Gebaut in `905efa0`.

      **Die Grenze läuft am Menü, nicht am Eintrag**, und darin liegt der
      Unterschied zu `02914d5` weiter unten: Dort lernte der ausgegraute
      Eintrag, **warum** er ausgegraut ist — das war richtig und bleibt es. Nur
      trägt es nicht, wenn *jeder* Eintrag grau ist: Der Satz erklärt dann
      nichts mehr, er wiederholt sich neunundsechzigmal. Ein gemischtes Menü
      behält seine grauen Zeilen samt Grund, denn dort steht die Erklärung
      **neben einem Eintrag, der geht**, und dieser Vergleich sagt dem Kunden
      mehr als das Verschwinden. Die Werkzeugzeile bleibt aus demselben Grund
      unangetastet — sie nennt den Grund im Klartext, und dort sieht ein
      Anfänger zuerst hin.

      Damit sind es drei Lagen: Startbildschirm 2 Menüs, leere Szene 5, mit
      einem gewählten Körper wieder alle 9.

      **Die Hälfte der Antwort gab es schon, und niemand wusste davon.**
      `_workspace_menus` (`main_window.py:1425`) tut auf dem Startbildschirm
      dasselbe, seit Monaten, mit derselben Begründung im Docstring —
      „siebzig Einträge, von denen dort keiner etwas tut, sind keine Auskunft,
      sondern Kulisse“. Der erste Testlauf schlug deswegen fehl: Er maß den
      Startbildschirm und fand dort alles schon ausgeblendet. **Wer eine Regel
      neu erfindet, sollte zuerst suchen, ob sie an einer Nachbarstelle schon
      steht** — hier waren es zwei Sitzungen, ein halbes Jahr auseinander, mit
      demselben Gedanken und demselben Bild dafür.

      **Und eine Falle, die 3d-druck-3a vierundfünfzig Fixture-Fehler
      gekostet hat:** Der erste Anlauf ging über `menuBar().actions()` und fasste
      dabei ein `QMenu` an, dessen C++-Seite fort war — dieselbe Falle wie in
      `overlay.py`, nur an einer frisch gebauten Stelle. Die Liste, die die
      Menüs am Leben hält, heißt `self._menus`; über die läuft es jetzt. Dazu
      kam eine PySide6-Stub-Falle: `QAction.menu()` ist als `QMenu` deklariert
      statt als `QMenu | None`, also hält mypy ein `is None` für toten Code.
      `if not menu:` geht durch.

## Was ein Kunde beim Öffnen der Beispiele sieht (23.08.2026)

Nicht „laufen sie" — das prüft `test_examples.py` seit langem. Sondern: Was
steht daneben, wenn jemand das erste Mal ein mitgeliefertes Beispiel öffnet.
Neun Dateien, jede geladen, ausgewertet und der Prüfbericht angesehen.

    fünf von neun begrüßen mit Warnungen, zusammen elf
    zehn davon:  perceive.generated_lost
    einer:       repair.components_removed
    Fehler:      keine

- [ ] **Vier Stapel zeigen auf `session.py:1515` — die Stelle ist benannt,
      die Ursache nicht.** Gesammelt am 23.08.2026 von drei Sitzungen
      unabhängig: 3d-druck-33 in einem Torlauf, b8 in einem zweiten, 64 nach
      sechzehn Tests, und b8 ein viertes Mal aus `test_operation_ui.py`.

      **Der vierte ist der aufschlussreichste**, weil er aus einer anderen
      Datei kommt und den Weg zeigt:

          conftest.py:255       _no_worker_outlives_its_window
            -> main_window.py:7099   release
              -> main_window.py:7060   wait_for_workers
                -> session.py:1515       wait_for_idle

      Das ist die **Aufräum-Fixture**, und sie läuft nach jedem Test in jeder
      Fensterdatei. `1515` sah nach einer Eigenheit von `test_ui.py` aus, weil
      die Tests dort `wait_for_idle` auch selbst rufen — 110-mal. Über den Abbau
      erreicht es **jede** Fensterdatei, ob sie es selbst ruft oder nicht.

      **Und jetzt der Vorbehalt, der die vier Stapel entwertet** (3d-druck-33,
      nachdem sie ihren eigenen Befund gegen diesen Einwand gelesen hatte):
      `wait(50)` blockiert in C, der Hauptthread führt dort keinen Bytecode
      aus, sein Rahmen wandert nicht. **Jeder Abzug, der während dieser
      fünfzig Millisekunden entsteht, zeigt `1515` — gleich was den Prozess
      umbringt.** Vier Stapel an einer Stelle, an der der Rahmen die meiste
      Zeit steht, sind keine vier Zeugen; sie sind ein Zeuge, viermal gefragt.

      **Der Speicherbereiniger ist Begleitumstand, nicht Ursache**, und das
      sagen zwei Messungen zu verschiedenen Zeiten dasselbe:

      | Stand | ohne Schutz | mit Schutz |
      |---|---|---|
      | 14.08., `gc.disable()` prozessweit | 1 von 8 | 5 von 24 |
      | 23.08., Schutz um `wait(50)` | 3 von 3 gerissen | 2 von 2 gerissen |

      **Warum der Schutz an einer Stelle wirkt und an der anderen nicht**, ist
      die brauchbare Hälfte des Abends:

      | Wo | Was währenddessen läuft | Schutz wirkt |
      |---|---|---|
      | um `processEvents` | Qt stellt Ereignisse an Widgets zu | **ja**, 6/8 → 1/8 |
      | um `wait(50)`, global | der Hauptthread wartet, sonst nichts | **nein** |

      Der Schutz um `processEvents` wirkt, **weil dort ein Vorgang läuft, den
      der Sammler stören kann**: Qt hat ein Widget in der Hand, der Sammler
      räumt es ab. Bei `wait(50)` gibt es diesen Vorgang nicht; ein
      `gc.disable()` verschiebt dort nur, wann gesammelt wird. Damit steht die
      Messung vom 14.08. **nicht** gegen die vom 22.08. — sie beantworten
      verschiedene Fragen, und beide richtig.

      **Was bleibt:** ein Arbeiter, der im Plattencache allokiert
      (`cache.get` → `numpy.load` → `zipfile`), während das Fenster abgebaut
      wird. Das ist eine **Lebensdauerfrage, keine Sammlerfrage**, und die
      Aufräum-Fixture steht mitten darin. Wer hier weitermacht, fängt dort an
      und nicht beim `gc`.

      **Nachtrag vom 24.08.2026 — der erste kontrollierte Griff.** 3d-druck-bd
      meldete einen Riss **mitten im Lauf** statt beim Abbau, und damit erstmals
      mit einem Namen: `test_ui.py::test_cancelling_the_question_keeps_the_window_open`.

          allein, 3×                    Exit 0, 0, 0
          ganze Datei, 3×               Exit 127 (2× exakt bei 28 %)
          erste 98 Tests, 3×            Exit 127
          erste 49 / 24 / 9 Tests       Exit 0

      Ein `-p`-Plugin bog `disk_backed_cache` auf `ResultCache()` ohne Platte um
      — an **beiden** Stellen, weil `session.py` den Namen direkt importiert.
      **Abwechselnd gefahren**, nicht in Blöcken:

          Runde 1:  mit Platte Exit 127   |   ohne Platte Exit 0
          Runde 2:  mit Platte Exit 139   |   ohne Platte Exit 0
          Runde 3:  mit Platte Exit 139   |   ohne Platte Exit 0

      Dazu drei Vorläufe je Seite in Blöcken: **6 von 6 rot mit, 6 von 6 grün
      ohne.** Die Blöcke allein hätten auf einer Maschine mit sechs Sitzungen
      eine Aussage über die Uhrzeit ergeben.

      **Nachtrag vom 24.08.2026 (3d-druck-61), bei ruhiger Maschine.** Null
      fremde Python-Prozesse, 42 GB frei, gleicher HEAD, gleicher Interpreter:

          Hauptbaum F:\3D Druck                     3/3 Absturz
          Hauptbaum, ohne pytest-Cache              Absturz
          Hauptbaum, eigener Bytecode-Ort           1 grün / 2 Absturz
          Worktree C:\…\Temp                        4/4 grün
          Worktree F:\wl-probe-f                    2/2 grün
          Worktree "F:\wl probe mit luecke"         2/2 grün
          Worktree F: + .venv als Junction daneben  2/2 grün

      Damit sind **ausgeschlossen**: Fremdlast (die eigene Hypothese des
      Messenden, ausdrücklich zurückgenommen), das Laufwerk, ein Leerzeichen im
      Pfad, der Bytecode-Cache, der pytest-Cache und die `.venv` im Baum. Übrig
      bleibt etwas am konkreten Verzeichnis `F:\3D Druck` — Vermutung und nicht
      mehr: ein Virenscanner oder Indexdienst, der dieses bekannte Verzeichnis
      beobachtet und einem frisch angelegten Pfad noch nicht folgt. Ohne
      Adminrechte nicht messbar.

      **Und eine Falle, die im Vorbeigehen entstand:** Der erste Lauf mit
      `PYTHONPYCACHEPREFIX` war grün, der zweite und dritte rot. Wer nach dem
      ersten aufhört, schreibt einen Fehlbefund ins Register.

      **Praktische Folge für alle Sitzungen: Wer `test_widget_lifetime` misst,
      nimmt einen eigenen Arbeitsbaum.** Im Hauptbaum ist er reproduzierbar
      rot, ohne dass der Code etwas dafürkann.

      **Nachtrag vom 24.08.2026 (3d-druck-b0): wer im geteilten Baum misst,
      während jemand schreibt, misst nichts.** 3d-druck-43 fand ein billiges
      Reproduktionspaar — `test_sketch_editor.py` plus `test_translations.py`
      in einem Prozess, Exit 139 in neun Sekunden statt in fünfundzwanzig
      Minuten, und `test_translations.py` ist nicht einmal eine Fensterdatei.
      Nachgemessen:

          Hauptbaum, während fremde Änderungen uncommittet dastanden  3 von 6 rot
          eigener Arbeitsbaum auf demselben HEAD, ohne sie            0 von 6 rot
          jede der beiden Dateien allein                              je 0 von 3
          nach dem Commit, im Wechsel gemessen, beide Bäume           0 von 10 rot

      **Derselbe Hauptbaum, der 3 von 6 riss, ist danach 0 von 5.** Geändert
      hat sich nicht der Ort, sondern dass die Dateien nicht mehr mitten im
      Lauf geschrieben wurden — `sketch_editor.py`, `viewport.py`, `pins.py`
      und `mesh.py` standen während der ersten Messung als geändert da. Python
      lädt Module beim Import; ändert sich eine Datei zwischen zwei Testdateien
      im selben Prozess, ist jedes Ergebnis Zufall.

      Das Paar bleibt als **Werkzeug** brauchbar (neun Sekunden statt
      fünfundzwanzig Minuten), ist aber **kein bestätigtes Reprodukt** der
      Familie: unter kontrollierten Bedingungen 0 von 11. Was nach dem
      rtree-Ausbau sicher bleibt, ist `test_ui.py` — 2 von 2, im eigenen Baum
      gegengeprüft.

      **Nachtrag vom 24.08.2026 (3d-druck-61): jedes zusätzliche Fenster im
      Prozess hebt die Rate.** Beim Fix für das Viewport-Bild im Fehlerbogen
      gemessen, je eigener Arbeitsbaum auf demselben HEAD, `tests/test_ui.py`:

          ohne alles                  2 Abrisse von 9
          Fix ohne die neuen Tests    1 von 3
          Fix mit zwei neuen Tests    2 von 3
          Endfassung, ein Test        1 von 3

      Der teure Test baute über die `window`-Fixture ein ganzes `MainWindow`,
      nur um zu prüfen, dass `snapshot` ohne Plotter `None` gibt — zwei
      zusätzliche VTK-Fenster in einem Prozess, der ohnehin am Limit ist. Für
      diese Frage genügt ein nacktes `QWidget`, und mit ihm fällt die Rate
      zurück auf die Grundrate.

      **Daraus eine Regel, die keine Messung mehr braucht:** Wer einen Test
      schreibt, der ein `MainWindow` baut, erhöht die Abrissgefahr **der ganzen
      Datei** — nicht nur seines eigenen Falls. Ein Test, dessen Frage ein
      nacktes Widget beantwortet, bekommt kein Fenster.

      **Nachtrag vom 24.08.2026 (3d-druck-b0): zwei Bäume, ein Inhalt, zwei
      Ergebnisse.** Beim Messen des Fensterfixes fiel derselbe Riss an —
      `0xc0000374` (Heap-Korruption) mitten im `Garbage-collecting`,
      reproduzierbar 3 von 3 im Hauptbaum. Im eigenen Arbeitsbaum dagegen 4 von
      4 grün, **auch nachdem alle uncommitteten Änderungen des Hauptbaums dort
      eingespielt waren** — inhaltsgleich, Bytecode-Cache in beiden vorhanden.
      Damit ist der Code als Ursache ausgeschlossen und die Deutung unten
      gestützt: Es ist der Zustand der Maschine, nicht die Zeile.

      **Und die Deutung ist die Hälfte, auf die es ankommt** (3d-druck-33, am
      Code gelesen statt gemessen): **Der Plattencache ist die Bedingung, nicht
      die Ursache.** `DiskCache.get` macht echte Datei-I/O (`read_text`,
      `read_bytes`), und **Datei-I/O gibt den GIL frei**. Ohne Platte kopiert
      der Arbeiter Python-Objekte und hält den GIL durchgehend — der Hauptthread
      kommt gar nicht dran, es gibt kein Nebeneinander, das man zerreißen
      könnte. Mit Platte gibt der Arbeiter ihn bei jedem `read_bytes` ab, und
      **genau in diesem Fenster** läuft der Hauptthread in `processEvents`.

      **Wer hier weitersucht, sucht nicht in `cache.py`** — dort ist kein
      Fehler. Das naheliegende Leck ist ebenfalls ausgeschlossen:
      `MeshData.from_bytes` schließt sein Zip (`with np.load(...) as data`).
      Die Ursache liegt darin, was Qt und der Arbeiter in diesem GIL-Fenster
      miteinander tun.

      **Die Größenschwelle passt dazu und ist keine Ansammlung von Speicher,
      sondern eine von Gelegenheiten:** Je mehr Fenster und Netze im Spiel sind,
      desto öfter fällt ein GIL-Fenster mit einem Zustellvorgang zusammen.

      **Die nächste Messung ist benannt** (3d-druck-33, nach dem Bau): ein
      Cache, der die Bytes im Speicher hält, aber `codec.loads` samt `np.load`
      durchläuft. Reißt es damit, genügt die Allokation; reißt es nicht, ist es
      wirklich die Datei-I/O.


- [x] **Nach einem weiten Verschieben dreht die Kamera um den alten Punkt.**
      Robert am 23.08.2026: „nach jedem verschieben springt die kamera und das
      modell immer komisch“, und die Entscheidung gleich dazu: „kamera bei
      aktueller position dann immer lassen“. Gebaut von 3d-druck-64 in
      `e550b9b`, und zwar in der kleinen Variante, weil Robert davorsaß.

      Zwei Wege führten dorthin, und der zweite war der sichtbare:
      `outgrown()` prüft *gewachsen* **oder** *weggerückt* — das zweite trifft
      auf jeden geschobenen Körper zu —, und `_centre_rotation()` setzte bei
      jedem Aufbau den Fokus auf die Mitte der Körper und rückte die Kamera
      mit. Beide fragen jetzt dasselbe: Standen dieselben Objekte schon da?

      **Der Preis, den 64 selbst benannt hat:** Bis zum nächsten echten
      Szenenwechsel wird um den alten Punkt gedreht. Er fällt erst auf, wenn
      jemand weit schiebt **und dann** dreht.

      **Die saubere Fassung setzt den Fokus beim Beginn einer Drehung** statt
      bei jedem Aufbau. Sie ist nicht viel Arbeit, aber sie ändert das
      Kameraverhalten — mitten vor einem Bau, in genau dem Bereich, den Robert
      an einem Tag dreimal gemeldet hat. Deshalb danach und nicht davor.

      **Gebaut (3d-druck-43, 26.08.2026), 0.1.5 ist draußen.** Der Drehstart
      (`_left_down`/`_right_down` im Interaktionsstil, schwacher Rückruf
      `on_rotate_start`) rückt den Fokus auf den Punkt des Sichtstrahls, der
      der Mitte der Körper am nächsten liegt (`rotation_focus`,
      `viewport.py`): Stellung und Blickrichtung bleiben, das Bild ändert
      sich um nichts, nur die Tiefe des Drehpunkts stimmt wieder — kein
      Sprung, weder beim Aufbau noch in der Geste. `_centre_rotation` und
      damit das Nachrücken beim Aufbau sind ersatzlos weg; `_moved_only`
      bleibt für `outgrown`. Tests: `rotation_focus` in drei Lagen plus die
      Kette bis in die Kamera (`test_viewport_decisions.py`).

- [x] **Ein Klick auf eine 5,19-mm-Bohrung schlägt M3 vor, und M3 trägt dort
      nichts ab.** Gemessen am 23.08.2026 im laufenden Fenster, `plate_holes.stl`,
      Bohrung `hole_1` gewählt:

      | Operation | Vorgabe | Bohrung dazu |
      |---|---|---|
      | Heat-Set-Einpressbuchse | **M3** | 4,00 mm |
      | Mutternfalle | **M3** | — |
      | Gewinde | **M6** | 8,00 mm |

      Aus der Normteiltabelle: M3 → 4,00 mm, **M4 → 5,60 mm**, M5 → 6,40 mm,
      M6 → 8,00 mm. Die Anwendung kennt den Durchmesser — er steht in
      `feature.params["diameter"]` — und sagt ihn nicht.

      **Die Folge ist keine schlechte Passung, sondern gar nichts.**
      `heatset_m4` ist `subtractive=True`: Der Baustein *bohrt* die
      Buchsenbohrung, er setzt keine Buchse ein. Ein 4,00-mm-Schnitt liegt
      vollständig innerhalb einer 5,19-mm-Bohrung, die Einführfase (4,60 mm)
      ebenfalls. Der Kunde klickt, füllt den Dialog aus, bestätigt — und
      bekommt einen Schritt im Verlauf über einer unveränderten Geometrie.
      Richtig wäre M4, die kleinste Größe oberhalb von 5,19.

      **Warum es so ist, und warum das keine Nachlässigkeit war:**
      `values_for` (`app/core/scene/placement.py:67`) kehrt bei `at_feature`
      sofort zurück, und der Docstring begründet es:

      > „Nicht seine Größe — eine Senkung nimmt den Durchmesser des
      > Schraubenkopfs, nicht den der Bohrung, auf der sie sitzt, und eine
      > hilfsbereit eingetragene 5,2 wäre dort eine falsche Zahl, die wie eine
      > gemessene aussieht.“

      **Für die Senkung stimmt das vollständig.** Der Unterschied ist fachlich:
      Eine Senkung *sitzt auf* der Bohrung, eine Einpressbuchse *ersetzt* sie.
      Eine Regel, die für den einen Fall richtig ist, deckt den anderen mit —
      und weil sie richtig begründet ist, liest man darüber hinweg.

      Gefunden als Gegenprobe zu `at_hole` (3d-druck-3a, `2f66440`): Die sieben
      Einträge kommen alle im Kontextmenü an, sind alle bedienbar und lösen
      alle aus — der Anschluss steht. Nur der Schritt danach fehlt.

      **Behoben am 25.08.2026, in zwei Hälften.** Die Baustein-Hälfte war
      schon vorher gefallen und stand hier zu lange als offen:
      `size_for_insert` / `size_for_nut_trap` / `size_for_thread`
      (`fasteners.py`, `6f064792`) wählen seit dem gemessenen M3-Fall die
      passende Größe zur Bohrung. Heute kam die Senkungs-Hälfte dazu:
      `screw_for_bore` ordnet die gemessene Bohrung über das
      Durchgangsloch-Band ihrer Schraube zu (5,19 → M5), die Senkung nimmt
      deren Kopf statt der Schemavorgabe, und `bore_advice` nennt den
      gemessenen Durchmesser im Dialog — als Satz, wo eine Größe passt, als
      Frage mit den Nachbargrößen, wo keine passt. Angeschlossen in
      `run_operation` (Freigabe 3d-druck-43), geprüft in `test_matching.py`
      (35 Fälle, kein toter Bereich über 1,0–12,0 mm) und
      `test_placement.py`. Die Zuordnung sitzt damit an zwei Orten, und das
      ist fachlich: Die drei bausteinbezogenen Fragen in `fasteners.py`
      (ersetzt die Bohrung → gemessenes Maß), die schraubenbezogene in
      `placement.py` (sitzt auf der Bohrung → Kopf der Schraube).

- [x] **Die Figur in „Weg 4" stand 0,29 mm unter der Druckplatte — behoben
      am 23.08.2026 (`abce5f3`).** Das weiche Verschmelzen mit Radius 4 rundet
      auch nach unten ab. Der Prüfbericht sagte es als **Hinweis**, und das ist
      dort richtig: `_severity_for` wiegt die Lage leichter als die Größe, weil
      ein Klick sie behebt — beim Schreiben kippt dieselbe Rechnung zur
      Warnung, denn dann ist der Klick nicht passiert. Der Weg endet jetzt mit
      `place_on_bed`; §2.2 nennt „stellen" ohnehin als seinen Teil.

      **Zwei Tests fielen dabei um, und beide waren die eigentliche Beute.**
      `test_the_way_ends_in_a_printable_file` prüfte `st_size > 0` — „druckfertig"
      hieß damit „die Datei ist nicht leer", und eine Datei entsteht auch für
      ein Teil unter der Platte (CuraEngine schreibt sie sogar).
      `test_the_strokes_survive_the_file` griff auf `ops[-1]` zu und brach,
      sobald der Weg einen Schritt länger wurde, obwohl an den Zügen nichts
      anders war: **Ein Bezug auf „den letzten" ist eine Aussage über die Länge
      der Kette**, und die war dort nie das Thema. Er sucht den Schritt jetzt
      über seinen Namen — dieselbe Lehre wie bei den Katalogeinträgen.

- [x] **Zweimal gespeichert waren zwei verschiedene Dateien — behoben am
      23.08.2026 (`efd79ae`).** Jeder Lauf von `tools/make_examples.py`
      erzeugte neun geänderte Beispieldateien, obwohl sich an keinem Beispiel
      etwas geändert hatte. Der Inhalt war Zeichen für Zeichen gleich; die
      Bytes waren es nicht.

      **Es sind die ZIP-Zeitstempel.** Ein Container schreibt je Eintrag ein
      Änderungsdatum aus der Uhr. Für einen Kunden folgenlos — er sieht das
      Datum der Datei, nicht das der Einträge darin. Für alles, was Dateien
      *vergleicht*, ist es Rauschen: neun Zeilen Verlauf ohne Inhalt bei jedem
      Erzeugungslauf, und in einem Baum mit vier Sitzungen neun Dateien, die
      aussehen, als hätte jemand daran gearbeitet.

      **Der Test dazu stand schon da und hieß, was er nicht prüfte:**
      `test_a_second_round_trip_writes_the_same_bytes` verglich die *Einträge*
      im Container, und die waren immer gleich. Er kann jetzt einlösen, was er
      heißt. Daneben steht ein zweiter, der die **Ursache** prüft statt der
      Wirkung — der erste würde auch grün, wenn zwei Läufe zufällig in dieselbe
      Sekunde fielen, und an einer schnellen Maschine tun sie das fast immer.

- [x] **Bausteinmerkmale verwaisen beim ersten Folgeschritt, weil die
      Erkennung sie nie gesehen hat — behoben am 23.08.2026 in zwei Schritten
      (`d28f145`, `94650dc`).** Gemessen an „Dose mit Deckel", dem
      eigenen Vorzeigebeispiel — fünf von neun Beispielen begrüßen deshalb mit
      einer Warnung.

      **Der Punkt hieß zuerst „Eine Textprägung frisst alle benannten
      Merkmale", und das war das Symptom.** Die Ursache hat 3d-druck-3a
      gemessen, und sie widerlegt beide Vermutungen, die davor standen — weder
      wandernde Bezugsgrößen noch die Prägung selbst:

          Schritt 4 (insert_heatset_m4)  Objekt 17 Merkmale, davon 4 Bohrungen
                                         frisch erkannt 13, davon 1 Bohrung
          Schritt 5 (label_text)         Objekt 15, frisch 15 — identisch

      **Schon nach Schritt 4 sieht die Erkennung nur eine der vier Bohrungen.**
      Die drei anderen sind Bausteinbohrungen; sie stehen im Objekt, weil
      `declared` sie direkt aus der Ausgabe der Operation nimmt. Beim nächsten
      Schritt wandern sie nach `carried`, und dort greift die Dreiteilung aus
      `b76df19`: Was eine erkennbare **Art** hat, wird zugeordnet und fällt
      heraus, wenn es keinen Partner findet. Ein `hole` ist erkennbar — also
      verwaisen sie. **Nicht weil sie weg sind, sondern weil die Erkennung sie
      nie gesehen hat.**

      `label_text` ist damit unschuldig; es ist bloß der erste Schritt nach dem
      Baustein, und **jede** Folgeoperation hätte dasselbe getan. Gegengeprobt
      wurde auch die Erkennung selbst: Zusammenfassung, Gewindestapel,
      Verrundungstrennung und Krümmungssegmentierung einzeln abgeschaltet — der
      Verlust bleibt in jeder Kombination. Die Bezugsgrößen wandern um 0,025 mm
      bei 105 mm Diagonale, also 0,02 Prozent; das erklärt nichts.

      **Der Fix gehört nach `_with_features` und ist eine Zeile Bedeutung:**

          checked = {name: f for name, f in carried.items() if f.kind in DETECTABLE_KINDS}

      Gefragt wird „ist die **Art** erkennbar", gemeint ist „wurde **dieses**
      Merkmal je erkannt". Der Unterschied ist heute willkürlich: Ein Gewinde
      reist ungeprüft mit, weil `thread` nicht in `DETECTABLE_KINDS` steht;
      eine Einpressbuchsen-Bohrung reist nicht mit, weil `hole` drinsteht —
      obwohl beide aus demselben Baustein kommen und beide für die Erkennung
      unsichtbar sind.

      **Behoben am 23.08.2026 (`d28f145`):** `Feature.recognised` hält fest, ob
      die Erkennung dieses Merkmal an seiner Stelle wiederfindet — gesetzt beim
      Einhängen über dieselbe Zuordnung, die auch sonst zuordnet. Die neun
      Beispiele gingen damit von **elf Warnungen auf sechs**, von fünf
      betroffenen auf vier.

      **Der zweite Teil bleibt offen, und die Messung danach hat ihn
      verschoben.** `heatset_m4_bore_1` verschwindet weiter lautlos — das
      einzige der vier, das die Erkennung *sieht*. Nachgemessen liegt es nicht
      am Melden:

          previous vor dem Schritt   14 Merkmale, darunter
                                     hole_1              (erkannt)
                                     heatset_m4_bore_1   (vom Baustein benannt)
          zugeordnet auf das neue hole_1:  hole_1
          heatset_m4_bore_1:               verwaist

      **Beide beschreiben dasselbe Loch.** Der Baustein benennt es beim Bauen,
      die Erkennung findet es und gibt ihm einen zweiten Namen — und beide
      reisen mit. Beim nächsten Schritt konkurrieren sie um dasselbe neue
      Merkmal, und das benannte verliert.

      Damit war die Frage nicht „warum fehlt der Befund", sondern **„warum
      trägt eine Bohrung zwei Namen"** — ein Befund wäre an dieser Stelle sogar
      falsch gewesen: Das Merkmal ist nicht fort, es steht als `hole_1` daneben.

      **Entschieden und gebaut am 23.08.2026 (`94650dc`):** Die Erkennung
      überspringt ein Merkmal, das an derselben Stelle schon einen Namen trägt.
      Gemessen über drei Beispiele trug in zweien jedes zweite bis dritte
      benannte Merkmal einen solchen Zwilling (4 von 13, 3 von 4) — nach dem
      Fix keines mehr.

      **Gefiltert wird gegen `declared` und ausdrücklich nicht gegen
      `carried`, und dieser Unterschied ist der Kern:** Dieselbe Zuordnung,
      dasselbe Ergebnis, zwei Bedeutungen —

          aus declared   zusätzlich in der Szene   -> ein Zwilling, filtern
          aus carried    derselbe, neu erkannt     -> sein Nachfolger, filtern wäre falsch

      Ein Filter gegen `carried` hätte die Partner entfernt, an denen die
      benannten Merkmale hängen: dasselbe Symptom mit umgekehrtem Vorzeichen.
      3d-druck-3a hat ihren eigenen Vorschlag daraufhin zurückgenommen und den
      Satz dazu geliefert: *„Ich habe `match(previous, detected)` als
      Zwillingssuche gelesen, wo es eine Nachfolgersuche ist."*

      **Nur eindeutige Paare** — `ambiguous` bleibt draußen, denn bei einem
      Gleichstand weiß niemand, welches erkannte Merkmal das benannte meint,
      und dann sind zwei Namen besser als ein falsch gelöschter.

      **Die Bilanz über die neun Beispiele:**

          zu Beginn        elf Warnungen, fünf von neun Beispielen
          nach recognised  sechs,         vier von neun
          nach diesem Fix  drei,          drei von neun

      Zwei der drei haben recht (die Deckfläche beim Aushöhlen, das Kleinstteil
      in Weg 3, das die Reparatur vorführt). Übrig bleibt `nut_trap_bore_1` im
      Gehäuseboden.

      Warum es mehr ist als eine Warnung zu viel: Passungen suchen ihr
      Gegenstück über benannte Merkmale (§14). Ein Beispiel, das eine
      Einpressbuchse setzt und danach ihren Namen verliert, hat die Passung
      verloren.
- [x] **Eine Mutternfalle bekam einen zweiten Namen, weil `match` ein gutes
      Paar für eine billigere Summe opferte — behoben am 23.08.2026
      (`6d6cf7b`, 3d-druck-3a).** `linear_sum_assignment` minimiert die
      **Gesamtsumme** und kannte die Annahmeschwelle nicht:

          nut_trap_pocket_1 -> hole_2   3,281   verwaist
          nut_trap_bore_1   -> hole_1   3,742   verwaist
                                                bester wäre hole_2 mit 0,757

      Die Summe 7,02 ist kleiner als jede Lösung, die `hole_2` an die Bohrung
      gibt. **`hole_2` war frei, das Paar war eindeutig, es hatte keine
      Rivalen** — und beide verwaisten trotzdem. Was ohnehin abgelehnt würde,
      kostet vor der Optimierung jetzt so viel wie eine falsche Art; damit
      sieht sie, dass ein Paar über der Schwelle so wertlos ist wie gar keines.

      **Damit fiel auch die Erklärung, die hier stand:** Das Merkmal war von
      Anfang an sichtbar, `detect` fand es sofort, und `recognised=False` kam
      nicht daher, dass es unsichtbar *war* — sondern daher, dass `match` es
      nicht zuordnen **wollte**. Der naheliegende Fix („`recognised`
      zurücknehmen können") wäre ins Leere gelaufen und wurde deshalb nicht
      gebaut.

      **Der Zirkel war real und hat die Sache trotzdem aufgeklärt.** Die
      Doppelung wurde nur deshalb überhaupt gesehen, weil die Messung `cost()`
      benutzte — **eine Ebene unter `match()`**. Wer mit derselben Zuordnung
      misst, die auch filtert, sieht nichts; wer eine Ebene tiefer misst,
      sieht die rohen Kosten und damit das Paar, das die Optimierung
      weggeworfen hat.

      **Die Bilanz der Nacht über die neun Beispiele:**

          zu Beginn   elf Warnungen, fünf von neun Beispielen
          am Ende     zwei — und beide sagen etwas Wahres über das,
                      was sie vorführen

- [x] **(erledigt, ursprünglicher Text)** Eine Mutternfalle bekommt weiterhin
      einen zweiten Namen — und die Messmethode dafür hat einen Zirkel. Gefunden von 3d-druck-3a außerhalb
      der neun Beispiele (Platte, zwei Schraubenlöcher, Mutternfalle,
      Einpressbuchse), nachgemessen Schritt für Schritt am 23.08.2026:

          nach insert_nut_trap   5 benannt, 8 erkannt
              nut_trap_bore_1     recognised=False
              nut_trap_pocket_1   recognised=False
              erkannt: hole_1, hole_3      <- hole_3 ist neu, und es ist die
                                              Mutternfalle

      **`detect` sieht sie sofort.** Die Vermutung, sie werde erst später
      sichtbar, stimmt nicht. Was fehlschlägt, ist die **Zuordnung**:
      `match(declared, detected)` bildet das Paar nicht, also bleibt
      `recognised=False`, also greift der Filter aus `94650dc` nicht. Plausibel
      ist der Grund geometrisch — eine Mutternfalle ist Sechskanttasche **plus**
      Bohrung, und was `detect` als *ein* Loch sieht, entspricht keinem der
      beiden benannten Teile gut genug.

      **Der Zirkel ist der eigentliche Fund, und er betrifft jede weitere
      Messung an dieser Stelle:** Doppelungen werden mit `match(benannt,
      erkannt)` gezählt — und der Filter benutzt dieselbe Funktion mit
      derselben Schwelle.

      > Eine Doppelung, die der Filter nicht sieht, sieht die Messung auch
      > nicht.

      In einem Lauf, in dem `nut_trap_bore_1` und `hole_3` sichtbar dasselbe
      Loch beschreiben, meldet die Zählung „keine Doppelung" — nicht weil keine
      da wäre, sondern weil `match` das Paar nicht bildet. Das erklärt auch,
      warum eine Messung über alle Schritte aller neun Beispiele **null** ergab
      und daneben trotzdem ein Fall gefunden wurde.

      **Was zuerst zu klären ist**, bevor irgendetwas gebaut wird: Die 0,757,
      mit denen 3d-druck-3a das Paar am Endzustand belegt hat, kommen aus einer
      anderen Rechnung als die, die intern entscheidet — sonst hätte der Filter
      gegriffen. Sind beide `cost`, liegt der Unterschied im Bezugssystem
      (Zentrum, Diagonale, `old_centre`).

- [x] **Kein Test prüft, womit ein Beispiel den Kunden begrüßt.**
      `test_examples.py` prüft, dass jedes öffnet und rechnet, und
      `test_no_example_greets_with_a_contradiction` fängt Widersprüche. Elf
      Warnungen in den Vorzeigebeispielen sind an keiner Prüfung
      vorbeigekommen — sie sind an gar keiner angekommen.

      **Gebaut am 23.08.2026** (`09e7a93`, 3d-druck-33).
      `test_no_example_greets_the_customer_with_a_warning` prüft in **drei**
      Richtungen: eine Warnung ohne Eintrag ist rot, ein Eintrag ohne Warnung
      ist rot (damit eine gelöste Warnung ihre Zeile verliert), und ein Eintrag
      für ein Beispiel, das es nicht gibt, ebenso. Die Ausnahmeliste trägt 23
      Zeilen, jede mit eigenem Grund — keine Obergrenze, wie der Punkt es
      verlangt hatte.

      Der Mechanismus dafür steht schon: `SETTLED_BY` streicht Warnungen, die
      spätere Schritte beheben (`b5bd8d3`, „Zwei Beispiele begrüßten mit
      Warnungen, und beide hatten recht"). Was fehlt, ist die Prüfung, die
      neue auffallen lässt.

      **3d-druck-33 baut sie, und die Bauart ist die Entscheidung, nicht das
      Ob.** *Nicht* als Obergrenze: „höchstens elf Warnungen" wäre in einer
      Woche grün mit zwölf, weil jemand die Zahl anpasst — und grün, obwohl
      der Kunde elf Warnungen sieht. Eine Prüfung, die den heutigen Stand als
      Ziel festschreibt, ist eine Attrappe mit Zahl. Sondern als
      **Ausnahmeliste je Beispiel und Befundcode**, mit Grund und
      Registerpunkt daneben — dieselbe Bauart wie `known_gaps`. Eine *neue*
      Warnung ist damit sofort rot, und jede Ausnahme trägt ihren eigenen
      Satz, warum sie noch dasteht.

      **Mit einer Einschränkung, die den Unterschied zwischen den beiden
      Punkten hier festhält:** `perceive.generated_lost` kommt **nicht** in
      die Ausnahmeliste. Das ist kein hinnehmbarer Zustand, sondern ein
      gebrochenes Versprechen — eine Ausnahme dafür würde genau die
      Zusicherung stillstellen, um die es geht. Die Prüfung bekommt deshalb
      zwei getrennte Listen: hinnehmbare Begrüßungswarnungen mit Grund, und
      eine **leere** für alles, was eine Zusicherung bricht. Die zweite darf
      nie wachsen.

## Der Bedienweg von außen nachgefahren (21.08.2026)

Nicht der Kern geprüft, sondern der Weg: Was sieht jemand, der die Anwendung
zum ersten Mal bedient, und wo hört der Weg auf. Das Werkzeug dafür war
`tools/run_ui_audit.py` — 25 Durchläufe durch die laufende Oberfläche, 9
Projekte, 15 Modelle, ein Aufbau von Null. **Nichts ist gestolpert**, keine
Ausnahme. Dazu die Register-Abdeckung: 86 Operationen, 86 im Menü, 86 in der
Befehlspalette, 86 in der Kommandozeile.

Die gestufte Tiefe hält §2.4: Median drei Werte auf der Vorderseite. Über
vier stehen vierzehn Operationen, wenn man Position X/Y/Z als den einen Wert
liest, der sie ist — neun davon sind Bausteine, und ein Baustein braucht
Größe, Ort und Passung. Das ist keine Nachlässigkeit, sondern die Natur der
Kategorie.

### Behoben, jeder mit Test

- [x] **Ein Klick auf die offene Stelle bot keine Reparatur an.** `edge_loop`
      ist das Merkmal für eine offene Kante — genau die Stelle, die der
      Prüfbericht als „Das Modell ist an drei Stellen offen" meldet. Das
      Kontextmenü daran bestand aus Ausblenden. Dabei gibt es `repair`
      („Schließt Löcher"), es hatte sich nur für kein Merkmal angemeldet.
      §2.6 nennt das Kontextmenü „den kürzesten Weg vom Sehen zum Tun"; für
      den häufigsten Defekt führte er ins Leere. Jetzt
      `applies_to=("edge_loop",)`, und `test_registry_consistency.py` prüft
      die Gegenrichtung von `applies_to`, die vorher niemand prüfte.
- [x] **Die Senkung war die einzige Operation mit sechs Werten und leerer
      Rückseite.** Der Winkel steht auf 90 Grad, und der eigene doc-Satz sagt
      warum: „90 Grad bei metrischen Senkschrauben." Ein Normwert ist keine
      Wahl. Nach hinten gelegt hat `countersink_hole` jetzt dieselbe
      Vorderseite wie `drill_hole` und `plug_hole` — Durchmesser, Position,
      Achse.
- [x] **`ui-audit/` stand nicht in `.gitignore`.** Jeder Auditlauf legte den
      Ordner im Arbeitsbaum ab.

### Zwei Funde, die eine Entscheidung brauchen

- [x] **„Eingabe korrigieren" ist ein Satz und kein Knopf — erledigt, und
      zwar länger als gedacht (`568e0bd` vom 21.08., `ab6e75c` vom 23.08.).**
      Ursprünglich: `CORRECT_INPUT`
      ist mit 26 Verwendungen die häufigste Handlung des Kerns und trägt
      `primary=True` — einen Handler hat sie nicht. Bei `UserError` und
      `FileWriteError` bleibt damit nur Abbrechen, und `FileWriteError` trifft
      das Ende jedes Weges, den Export. **Das ist kein Regelverstoß:**
      `tests/test_ui.py` (`test_an_error_without_a_handler_still_offers_a_way_out`)
      definiert die Regel ausdrücklich als „entweder eine Handlung mit Wirkung
      **oder** ein Rat zum Lesen", und die Begründung daneben ist gut — ein
      Knopf, der nichts tut, ist schlimmer als keiner. Es steht hier, weil
      §2.1 „keine Sackgassen" verspricht und der häufigste Bedienfehler eine
      ist. Was ein Handler tun müsste, ist die offene Frage: Bei einem
      Parameterfehler den Dialog mit den Werten erneut öffnen; bei „andere
      Anzahl an Objekten" die Auswahl ändern, und das ist kein Dialog.

      **Beide Hälften stehen — und die erste schon seit dem 21.08.2026.**
      `CHANGE_SELECTION` („Andere Objekte wählen") kam am 23.08. dazu
      (`ab6e75c`) und hängt an `evaluate.missing_input` und
      `evaluate.too_few_inputs`. Der Handler für den **Parameterfehler**
      existierte da längst: `MainWindow._correct_after_error`
      (`main_window.py:6150`), verdrahtet als `"correct_input"` in
      `error_handlers()`, ruft `edit_operation(op_id, field)` mit dem Feld aus
      `ValidationError.field`. Gebaut in `568e0bd`, drei Tests fahren ihn.

      **Hier stand am 23.08. „halb erledigt", und das war ein Suchfehler von
      3d-druck-64 — er ist eine Ebene tiefer als der bekannte.** Gesucht wurde
      nach der Konstante `CORRECT_INPUT`; gefunden wurde nur die Stelle in
      `panels.py`, die sie *anbietet*. Die Verdrahtung läuft aber über den
      **Wert**: `"correct_input"` als Schlüssel im Handler-Verzeichnis. Eine
      Suche nach dem Bezeichner findet keine Verdrahtung, die über seinen
      Inhalt läuft.

      *Merksatz dazu, weil derselbe Fehler in dieser Nacht dreimal in
      verschiedenen Gestalten auftrat:* **Wer prüft, ob etwas angeschlossen
      ist, sucht nach dem, was am anderen Ende ankommt — nicht nach dem Namen,
      unter dem es losgeschickt wurde.**
- [x] **Ein angeklicktes Gewinde bietet nichts an — gebaut von 3d-druck-b8
      am 23.08.2026 (`64769bc`).** „Diesen Schritt ändern" steht im
      Kontextmenü am Merkmal, ganz oben; der Klick öffnet den Dialog der
      erzeugenden Operation und **ersetzt** ihren Schritt beim Übernehmen,
      statt einen zweiten anzulegen (§15.4). Vier Tests.

      **Eine Messung dabei erklärt, warum der Punkt so lange offenstand.**
      Der erste Testaufbau bohrte ein Loch und fand nichts anzuklicken:
      `created_by` wird nur für `provenance="generated"` gesetzt, und das gibt
      es an genau zwei Stellen — `knowledge/parts/build.py` und
      `geom/pins.py`. `drill_hole` deklariert nichts; was es hinterlässt,
      findet die Erkennung wieder, und ein erkanntes Merkmal ist `detected`.
      **Das Gewinde war damit nicht ein Beispiel neben anderen, sondern der
      erste Fall, an dem es überhaupt auffallen konnte.**

      **Die Ausnahme im Konsistenztest bleibt trotzdem stehen**, und das ist
      kein Rest, sondern die Entscheidung: `known_gaps` fragt `applies_to`,
      und über den Weg bleibt `thread` leer — der Klick nimmt den anderen der
      beiden Wege. Wer die Ausnahme streicht, weil das Gewinde jetzt etwas
      anbietet, macht den Test rot. Ihr Kommentar gehört in dieselbe
      Begründungsgruppe wie sphere und torus; an 33 gemeldet.

      Ursprünglich stand hier: `thread` entsteht
      wirklich — der Gewinde-Baustein gibt es zurück
      (`knowledge/parts/build.py`) —, und `REGISTRY.for_feature("thread")` ist
      leer. Welche Operation fachlich auf ein fertiges Gewinde gehört,
      entscheidet der Bauplan und nicht eine Prüfung; bis dahin steht das
      Merkmal als benannte Ausnahme im neuen Test, damit es beim Lösen
      auffällt statt zu verschwinden.

      **Entschieden am 22.08.2026, und anders als die Frage lautete.** Bauplan
      §21.2 antwortet nicht, welche Operation auf ein Gewinde gehört, sondern
      dass ein **erzeugtes Merkmal immer den Schritt anbietet, der es erzeugt
      hat**. Über `applies_to` wäre das eine neue Operation je Merkmalsart
      gewesen — über die Provenienz ist es ein Eintrag, der für alle gilt und
      neue Merkmalsarten von selbst mitnimmt. Bei einem erkannten Merkmal
      entfällt er, weil es keinen Erzeuger hat. Zu tun bleibt der Eintrag im
      Kontextmenü und das Herausnehmen der Ausnahme aus dem Konsistenztest.

### Was dabei über das Messen zu lernen war

`pytest -q` am Stück ist für diese Suite der falsche Weg, und das steht im
Docstring von `tools/run_suite_isolated.py` seit dem 18.08. Der Lauf sammelte
3,2 GB an und stand nach 56 Minuten noch; dateiweise sind es 16,5 Minuten.
Zweitens: **zwei Läufe gleichzeitig gehen nicht.** Elf Dateien fielen mit
pytest-Code 4 — Nutzungsfehler, nicht Testversagen —, weil daneben `ruff`,
`mypy` und ein zweiter `pytest` liefen und `conftest.py` die
Nutzerverzeichnisse aller Läufe in denselben Temp-Ordner biegt (§38). Allein
nachgefahren: alle elf grün.

Drittens, zur Wackelei von `test_performance.py`: Sie ist **keine**
Reihenfolgefrage. `pytest-randomly` ist in dieser Umgebung gar nicht
installiert, `-p no:randomly` also wirkungslos — zwei identisch konfigurierte
Läufe ergaben 19 grün und 5 rot. Reine Messschwankung an der 25-%-Schwelle,
wie der Punkt weiter oben es beschreibt.

## Neun heruntergeladene Modelle durch die ganze Kette (21.08.2026)

Nicht der Testkorpus und nicht die Beispiele: neun Dateien, die an einem
Nachmittag aus dem Netz kamen — drei Verbinderleisten, zwei Sockelplatten, eine
Kit-Card, ein Propellersatz, eine Ente und eine 3MF mit **52 Körpern**. Jede
einzeln, jede über die laufende Oberfläche, und jede über die ganze Kette:
einfügen, optimieren, ausbauen, rückgängig und wieder vor, als Projekt
speichern, zumachen, wieder aufmachen, weiterbauen, exportieren, das
Exportierte wieder einlesen.

Gefahren wurde durch die Menüeinträge und die Operationsdialoge, nicht am
Stapel vorbei: `import_action.trigger()`, `run_operation` mit ausgefüllten
Feldern und `accept()`, `action_save_as`, `action_open`, `action_export`. Nur
die Systemdialoge für Datei und Ziel sind vorbelegt statt geöffnet — die
gehören dem Betriebssystem, und ein Lauf, der auf sie wartet, wartet für immer.

Was gehalten hat: alle neun lesen ein, mit den Körperzahlen, die auch der Kern
sieht (1 bis 52). Alle neun speichern als Projekt, öffnen wieder und stehen
dabei Körper für Körper gleich. Alle neun exportieren als 3MF und als STL, und
alle neun lesen ihr eigenes Exportergebnis mit derselben Körperzahl zurück. Der
Stapel hält: rückgängig und wieder vor liefert dieselbe Geometrie. 52 Körper
brauchen für einen Ausbauschritt acht Sekunden — spürbar, aber innerhalb §31.

### Behoben, jeder mit Test

- [x] **Eine Beschriftung, die den Körper verfehlt, sagte nichts.**
      `boolean.without_effect` gibt es seit der Magnettasche, und jeder, der
      Boolesches rechnet, fragt danach — Bohren, Stopfen, jeder Baustein, die
      Skizzentasche. `label_text` nicht. Gemessen an einem Sockel, dessen
      Hüllquader in der Mitte hohl ist: „BASIS" graviert kam mit unverändertem
      Volumen **und** unveränderter Dreieckszahl zurück, ein Schritt stand im
      Verlauf, und der Prüfbericht hatte dazu keine Zeile. Erhaben wäre es
      schlimmer gewesen als graviert — dann stehen die Buchstaben als eigene
      Komponente neben dem Teil und reisen bis in den Export mit.
- [x] **Ein Schnitt, der nur streift, kam durch.** `without_effect` maß gegen
      `EPS_GEOM`, also gegen ein Rechenepsilon. Eine Bohrung Ø4,2, gesetzt auf
      die Mitte des Hüllquaders eines Rahmens, trug **0,002 mm³** ab statt 194
      — mehr als das Epsilon und trotzdem nichts, was jemand je zu sehen
      bekommt. Gemessen wird jetzt an der Düse: `Profile.smallest_printable_-
      volume` ist ein Stück Extrusionsbahn von einer Bahnbreite Länge
      (Bahnbreite² × Schichthöhe, 0,035 mm³ bei 0,4 mm Düse), und alle vier
      Aufrufstellen geben ihr Profil weiter. Ohne Profil bleibt es beim
      Epsilon — ein Aufrufer, der keinen Drucker kennt, soll keinen erfinden.
      Regel 7: die Grenze steht im Profil und nicht im Code.
- [x] **Die erste Druckplatte blieb leer.** Ein Körper, der tiefer ist als das
      Bett, reißt die Zeilengrenze auch auf einer leeren Platte — und wanderte
      dann auf die nächste, die genauso wenig hilft. Zwei Sockel von 231 mm
      Tiefe auf einem 220er Bett und zwei Platten: **beide** landeten auf
      Platte 2, aufeinandergestapelt und über den Rand hinaus, während Platte 1
      leer blieb. Bei drei Platten blieb sie es auch. Weitergeblättert wird
      jetzt nur, wenn auf der aktuellen Platte schon etwas liegt.
- [x] **Der Rat „eine Platte mehr würde helfen" stimmte oft nicht.** Derselbe
      Sockel bekam ihn bei einer, zwei und drei Platten — und mehr Platten
      hätten nie geholfen, weil 231 mm auf kein 220er Bett passen. Ein
      Vorschlag, der nichts löst, ist schlimmer als keiner (Regel 17):
      `_overfull` fragt jetzt, ob wenigstens **zwei** Körper der letzten Platte
      allein aufs Bett passen würden. Sonst bleibt es bei
      `arrange.out_of_build_volume`, und das sagt, was wirklich hilft — teilen,
      verkleinern, anderes Profil.
- [x] **Ein Verschweißen, das das Netz aufreißt, wird zurückgenommen.** Der
      Fund kam von einer Datei, die diese Anwendung **selbst geschrieben**
      hatte: das exportierte 拓展架-3MF trug 17186 Ecken und war wasserdicht,
      und dieselbe Anwendung meldete es beim Wiedereinlesen als „nicht
      geschlossen". Schuld war die Eingangsstufe: bei 0,28 µm Toleranz fielen
      **zwei** Ecken zusammen, und weil sie zu zwei Blättern derselben Fläche
      gehörten, entstand daraus eine Kante mit vier Nachbarn. Ohne Verschweißen
      blieb die Datei dicht — gemessen mit `normalise(..., weld=False)`.
      Verschweißen ist eine Reparatur, und eine Reparatur, die etwas kaputt
      macht, wird nicht angewendet: war das Netz vorher geschlossen und ist es
      danach nicht mehr, gilt der unverschweißte Stand, und
      `ingest.weld_skipped` sagt es. Der Testfall ist derselbe Fall in klein —
      zwei geschlossene Quader, die eine Fläche teilen.
- [x] **Mehrere Platten, ein Bett, alles ineinander.** Gemeldet als „bei
      Projekten mit mehreren Platten sehe ich trotzdem nur eine", und es war
      genau das: jede Platte hat ihren eigenen Nullpunkt, die Anordnung setzt
      Platte 2 an denselben Ort wie Platte 1, und der Viewport zeichnete ein
      Bett und darauf alles. Zwei identische Sockel lagen Punkt auf Punkt
      übereinander. „Alle" reiht die Betten jetzt mit `PLATE_GAP` nach +X
      auf (`plate_shift`), die Körper gehen mit, und eine gewählte Einzelplatte
      zeichnet wieder genau ein Bett an seinem Ort. Die erste Platte bleibt, wo
      sie war — eine Szene mit einer Platte sieht Bild für Bild aus wie vorher.
      Ein Klick rechnet über `plate_at` zurück in die Szene; ohne diese
      Umkehrung setzte ein Klick auf Platte 2 die Bohrung eine Bettbreite
      daneben, und weil dort meistens nichts ist, hätte er stumm nichts getan.

### Zur Frage nach dem Plattenmaß

Ja: der Viewport zeichnet Bett und Bauraum aus `profile.printer.build_volume`,
und `check_build_volume` prüft gegen dieselbe Zahl. Die Tabelle
(`app/core/knowledge/data/printers.toml`, 17 Profile) stimmt mit den
Herstellerangaben überein — Centauri Carbon 2 mit 256 × 256 × 256, Neptune 4
mit 225 × 225 × 265, A1 mini und MINI+ mit 180³, Prusa XL mit 360³, MK4S mit
250 × 210 × 220.

**Eine Falle bleibt, und sie ist keine der Tabelle:** Vorgabe ist
`generic-220`. Wer den Erststart abbricht oder ohne Drucker weiterklickt,
bekommt ein 220er Bett — und dann meldet jedes 231 mm tiefe Teil zu Recht
„über den Bauraum hinaus", nur über einen Drucker, den niemand gemeint hat. Mit
`centauri-carbon-2` verschwanden dieselben Warnungen restlos.

### Was auffiel und eine Entscheidung braucht

- [x] **Das Regal-Packen verteilte sehr ungleich.** 52 Körper auf acht erlaubte
      Platten ergeben 3 / 1 / 10 / 3 / 2 / 5 / 28 — die letzte trägt mehr als
      die Hälfte, weil eine Zeile, die einmal überläuft, nie wieder von rechts
      gefüllt wird. Nach Tiefe sortiert wird es nicht besser (1 / 2 / 3 / 7 /
      16 / 23), also ist die naheliegende Verbesserung keine. „Bewusst
      einfach" steht im Docstring und hat seinen Grund; ob sieben Platten für
      52 Teile in Ordnung sind, entscheidet der Bauplan und nicht das Gefühl.

      **Entschieden am 22.08.2026 (Bauplan §29): sie sind es nicht, und die
      Ursache sind die Zeilen.** Zeilenweise zu packen verschenkt über jedem
      kurzen Teil einen Streifen von der Tiefe des tiefsten Teils derselben
      Zeile; eine andere Sortierung verschiebt diesen Streifen nur — deshalb
      war die Messung „nach Tiefe sortiert wird es nicht besser" kein Zeichen,
      dass hier nichts zu holen ist, sondern der Beleg, dass die Sortierung
      nicht die Stelle war. Genommen wird eine Regel ohne Zeilen: jeder Körper
      an die hinterste, dann linkeste freie Stelle, an die er passt. Sie ist in
      einem Satz erklärbar und ohne Startwert, also bleibt die
      Vorhersagbarkeit, um die es dem Docstring ging. Abnahme ist eine Messung
      und keine Meinung: weniger Platten für dieselben 52 Teile, sonst bleibt
      es beim Zeilenpacken.

      **Gebaut am 22.08.2026, und die Messung hält.** `arrange_on_bed` legt
      jeden Körper an die hinterste, dann linkeste freie Stelle; die Kandidaten
      sind die leere Ecke und je belegtem Rechteck zwei, rechts daneben und
      davor. Für dieselben 52 gemischten Teile auf einem 256er Bett: **fünf
      Platten zeilenweise, drei ohne Zeilen** (22/16/14), 8,5 ms, zweimal
      gerechnet identisch. Die Abnahme steht als Test
      (`test_fifty_two_parts_need_fewer_plates_than_rows_did`) und nicht als
      Notiz — sie ist die Bedingung, unter der die Regel bleiben darf, also
      muss sie mitlaufen. Zwei weitere Tests halten die Regel selbst fest:
      dass gleich tiefe Teile nebeneinander in derselben Tiefe landen, und
      dass neben einem 200 mm tiefen Teil nichts dahinter wandert, solange der
      Streifen daneben frei ist. **Wo hinten ist, war die einzige offene
      Frage:** `app.ui.viewport.VIEWS` blickt für „Vorne" aus `-y`, also ist
      `+y` hinten — das alte Zeilenpacken füllte von vorn.
- [x] **Der Plattenwähler wohnte im Explodieren.** Er erschien erst ab zwei
      Körpern **und** zwei Platten, und er stand in der Explodier-Leiste — wer
      eine einzelne Platte ansehen wollte, suchte ihn unter einem Werkzeug, das
      Teile auseinanderzieht.

      **War beim Eintragen schon behoben**, am 21.08.2026 mit `4790527`, und
      stand trotzdem noch zweimal in dieser Datei — einmal als Punkt, einmal im
      Register. Der Wähler sitzt in `HeaderBar.show_plates`
      (`app/ui/header.py`), `explode_bar.py` verweist von der anderen Seite
      darauf, und `main_window.py` verdrahtet `plateChanged` auf
      `viewport.set_plate`. Auch die Zusatzbedingung ist fort: sichtbar macht
      ihn `many = plates > 1`, also die Plattenzahl allein — ein einzelner
      Körper auf Platte 2 von 3 nach einem Auto-Split ließ ihn sonst
      verschwinden. Nachgewiesen von 3d-druck-b8 am 22.08.2026 gegen den Code,
      nachgeprüft von 3d-druck-64. **Der Fund an dieser Stelle ist der Punkt
      selbst:** Die Übersicht am Kopf nennt sich „die Abkürzung, nicht die
      Quelle" — wer daraus Arbeit zieht, ohne den Punkt an seinem Ort gegen den
      Code zu halten, baut ein zweites Mal, was schon steht.
- [x] **Dieselbe Frage kam bei jeder Auswertung wieder, und das wurde
      schnell viel.** Gezählt über die ganze Kette: die Ente **8** Rückfragen
      bei **1** verschiedenen, der Propellersatz **32** bei **5**,
      ALL+PLATES **99** bei **7** — sechzehnmal „Welches Merkmal entspricht
      pin_1?", sechzehnmal `pin_2`, und so weiter. Es ist je Auswertung
      dieselbe Frage, weil die Antwort nirgends festgehalten wird. Anhalten und
      fragen ist Regel 21 und richtig; 99 modale Fenster für 7 Entscheidungen
      sind es nicht. Wo die Antwort hingehört, ist die eigentliche Frage: in die
      Operation (dann reist sie mit der Datei und die Auswertung bleibt
      reproduzierbar, §11.3), ins Dokument oder nur in die Sitzung. Das
      entscheidet der Bauplan.

      **Entschieden am 22.08.2026: in die Operation** — Bauplan §15.7. Die
      Entscheidung war leichter als die Frage klang, weil §15.1 keine zweite
      Möglichkeit offenlässt: Die Auswertung ist eine reine Funktion aus Stack,
      Quellen, Parametern, Profilen und Startwerten. Eine Antwort, die nur in
      der Sitzung lebt, wäre ein sechster Eingang — zweimal ausgewertet käme
      zweimal etwas anderes heraus, und genau dieser Vergleich ist ein
      Abnahmekriterium von P0. Zwei Stellen sagten es längst für ihren
      Einzelfall (die Einheitenrückfrage als Parameter von `load`, §17.1, und
      „die Op wird umgeschrieben" bei mehrdeutiger Zuordnung, §21.3); es fehlte
      der Satz ohne Einzelfall. Zu tun bleibt, dass `ctx.ask` die Antwort
      zurückschreibt statt sie zu vergessen.

      **Gebaut am 22.08.2026 mit `311134a`**, und zwar auf dem Weg, den die
      Rückfallstufen schon gingen: `OpResult.answered` →
      `EvaluationResult.answers` → `History.record_answers`. Der Unterschied
      steht in beiden Docstrings, weil er die Sache ausmacht — eine
      Rückfallstufe ist ein Vermerk, den die Auswertung nie zurückliest, eine
      Antwort ist eine Anweisung. Nachgeprüft von 3d-druck-64 an
      `types.py:918`, `evaluate.py:253` und `history.py:335`.

      **Das gilt für die Fragen, die eine Operation selbst stellt.** Was die
      **Zuordnung** entscheidet — die 99 Fenster für 7 Merkmale aus §21.3 —
      passt in keinen Parameter und braucht ein eigenes Feld an der Operation
      samt Formatänderung. Diese Hälfte steht weiter offen, unter „Die Antwort
      der Zuordnung steht nirgends".
- [ ] **Verrundung und Fase gehen auf einem Netz nicht — Konzept liegt vor,
      Entscheidung offen.** `konzepte/konzept-flaechenrueckgewinnung-2026-08.md`
      (`e5ef72f`, 3d-druck-3a, 23.08.2026), sieben Abschnitte.

      **Die Zahl, die es entscheidet:** Ein Netz hat keine Kanten im
      B-Rep-Sinn. Über `BRepBuilderAPI_Sewing` gemessen:

          108 Dreiecke  →  108 Flächen, 324 Kanten

      Jede Dreiecksseite wird eine Kante; ein `fillet` darauf verrundete
      nicht die Modellkante, sondern **jede Facette**. Das ist kein
      Umsetzungsproblem, das ist die Sache selbst.

      **Was es bräuchte, ist Flächenrückgewinnung** — erkannte Merkmale in
      analytische Flächen zurückverwandeln, deren Schnittkurven berechnen,
      vernähen, dann `fillet_edges` wie auf jedem exakten Körper. Fünf
      Schritte; der dritte trägt drei offene Fragen, und die schwerste ist
      die, die beim Schreiben des Konzepts erst gefunden wurde: **Was
      passiert mit den 10,7 %, die kein flächiges Merkmal tragen?** Drei
      Wege, keiner umsonst — als Freiform annähern (teuer, ungenau), den
      Körper zurückweisen (ehrlich, aber der Kunde steht wieder ohne Weg
      da), oder ein Zwitter aus exakten und facettierten Teilen, den der
      Bauplan nicht kennt.

      **Warum es jetzt überhaupt denkbar ist:** Schritt 1 — die Erkennung —
      deckt die Korpuskörper seit dem 23.08.2026 zu 89 bis 100 Prozent ab
      (flächige Merkmale gezählt, `edge_loop` herausgerechnet). Vor jener
      Nacht hätte er nur Ebenen und Bohrungen geliefert. **Die Vorarbeit
      für Reverse Engineering ist entstanden, ohne dass jemand sie so
      genannt hat.**

      **Zu entscheiden ist nicht „bauen wir das?“, sondern „ist das eine
      Phase wert?“** — gegen den höchsten Kundenwert im Register: **neun von
      neun** heruntergeladenen Modellen laufen dagegen. Robert vorgelegt am
      23.08.2026.

      **Der billige Zwischenschritt daraus ist gebaut** (`02914d5`): Der
      ausgegraute Eintrag sagt jetzt, **warum** er ausgegraut ist. Er nimmt
      der Entscheidung nichts vorweg.

      Ursprünglich: `NeedsSolidError` mit dem richtigen Satz. Kein Fehler;
      nur ist damit für ein
      heruntergeladenes Modell die halbe Kategorie *Formgebung* zu. Steht so im
      Bauplan („keine Verrundungen auf Mesh-Kanten vor dem B-Rep-Kern"), und
      dieser Lauf ist der Beleg, wie oft man dagegenläuft: bei jedem der neun
      Modelle wäre es der nächste Handgriff gewesen.

## Der Bildweg zum ersten Mal wirklich gefahren (21.08.2026)

Zwei Durchgänge hatten die Zusatzsoftware am Code geprüft, und beide waren
gründlich. Dieser hier hat sie **benutzt**: ein ComfyUI auf dieser Maschine
eingerichtet, die Gewichte geladen, ein Bild hineingelegt und gewartet, bis ein
Körper herauskam. Dreizehn Funde, und die Hälfte davon hätte kein Durchlesen
ergeben: ein Regelverstoß in einer Datendatei, eine Windows-Grenze, die
Geschwindigkeit des Rechners, auf dem es läuft — und zwei Fehler, die erst
entstanden, als der erste Fix da war.

Die Ausgangslage war die des Kunden, und zwar unfreiwillig: ComfyUI installiert
über den offiziellen Installer von comfy.org, Gewichte keine, Grafik eine
Intel-Arc-140V, und ein `qwen3:14b` bei Ollama.

### Der Weg, den ein Kunde am ehesten geht, war der einzige unbekannte

- [x] **ComfyUI Desktop wurde nicht gefunden.** Die Desktop-Anwendung ist das
      erste Angebot auf comfy.org, und sie legt ihr ComfyUI sechs Ebenen tief
      unter `AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI` ab.
      Keine der fünf geratenen Stellen trifft das; der Dialog sagte „an den
      üblichen Stellen nicht gefunden", und die Antwort lag daneben: Die
      Anwendung schreibt ihren Installationsordner in
      `%APPDATA%\Comfy Desktop\installations.json`, samt einem selbst
      gewählten. `_from_desktop` liest sie, tolerant — die Datei gehört jemand
      anderem, ihr Aufbau ist nirgends zugesagt, und eine Anwendung, die daran
      scheitert, wäre schlechter als eine, die weiter rät. Der Ort je Plattform
      steht in `_config_home(platform)`, mit der Plattform als **Parameter**:
      Sonst ist die Zuordnung nur dort prüfbar, wo sie gerade gilt, und mypy
      hält die anderen Zweige für unerreichbar.

- [x] **Die Paketliste nannte drei Pakete, und es fehlten sechs.** `trimesh`,
      `diffusers`, `scikit-image`, `lazy_loader`, `omegaconf` und die Laufzeit
      von `antlr4` — gemessen war die Liste an einer Installation, in der andere
      Knoten das übrige längst mitgebracht hatten. Gefunden wurden sie einzeln,
      indem der Knoten geladen wurde, bis er lud. Die Version an `antlr4` ist
      keine Übervorsicht: `omegaconf` liest damit einen vorkompilierten
      Automaten, und die 4.13 serialisiert ihn anders („Could not deserialize
      ATN with version 3"). Alle Lizenzen geprüft — BSD, Apache-2.0, MIT.

- [x] **„Fertig" war eine Behauptung.** Die Einrichtung kopierte, klonte,
      flickte und installierte, und ob am Ende etwas lief, erfuhr der Kunde
      erst beim Erzeugen: dann stand in ComfyUIs Protokoll „No module named
      'trimesh'" und im Dialog, der Knoten sei unbekannt. `nodes_load` sieht
      jetzt nach — im Python **von ComfyUI**, denn nur dort steht, was ComfyUI
      hat. Der Schritt kostet zwei Sekunden und steht **vor** den Gewichten:
      Ein fehlendes Paket nach zwei Sekunden zu melden ist mehr wert als nach
      einer halben Stunde Download.

### Ein Zeichen über der Grenze

- [x] **MAX_PATH ist 260, und der Pfad war 261.** `huggingface_hub` legt seine
      halbfertigen Dateien unter dem Ziel ab, und ihre Namen sind 163 Zeichen
      lang — Prüfsumme, Etag, Endung. Mit dem 98 Zeichen tiefen Ziel von
      ComfyUI Desktop macht das 261, und der Kunde bekam mitten im 7,5-GB-
      Download einen `FileNotFoundError` mit einem Pfad, den kein Mensch liest.
      `LongPathsEnabled` in der Registrierung ist eine Systemeinstellung und
      gehört keiner Anwendung; das Präfix `\\?\` half gemessen nicht. Geladen
      wird jetzt in einen kurzen Ordner und danach verschoben — auf demselben
      Laufwerk ein Umbenennen.

- [x] **Und der erste Fix löschte den Fortschritt.** Der kurze Ordner hieß
      `mkdtemp`, also jedes Mal anders, und ein `finally` räumte ihn auf. Damit
      war die Zusage im Docstring — „setzt beim nächsten Lauf fort" — eine
      Lüge. Gemessen an drei Abbrüchen hintereinander (`WinError 10054`, dann
      2 GB weit, dann `WinError 10038`); bei 7,5 GB über eine wackelige Leitung
      ist das der Normalfall und nicht das Pech. Fester Name, aufgeräumt wird
      nur Erfolg. Der Beweis kam beim vierten Anlauf: **59 Sekunden**, weil
      6,5 GB schon dalagen.

- [x] **Die Wiederholung stand im Kindprozess und konnte dort nichts
      bewirken.** `huggingface_hub` hält einen globalen HTTP-Client; sobald ein
      Fehler ihn schließt, antwortet jeder weitere Versuch im selben Prozess
      mit „Cannot send a request, as the client has been closed" — der zweite
      Anlauf scheiterte schneller als der erste und aus einem anderen Grund.
      `_run_repeatedly` startet jetzt je Anlauf einen **neuen** Prozess. Beim
      Freistell-Modell nachgewiesen: erster Anlauf nach 2 s tot, zweiter lud
      die 444,5 MB durch.

### Bereit war es nicht, und die Lizenz stand in der ersten Zeile

- [x] **`readiness()` fragte einen Knoten, wo der Ablauf sechs braucht.** Sie
      prüfte den Knoten aus unserer eigenen Sammlung — der lag nach der
      Einrichtung vor, also stand „Bereit" da, und abgeschickt scheiterte der
      Auftrag an einem *anderen* Knoten desselben Ablaufs. `missing_nodes()`
      nennt jetzt die Namen, denn „ein Knoten fehlt" schickt niemanden weiter
      (Regel 17).

- [x] **Der fehlende Knoten war GPL, und damit ein Verstoß gegen Regel 15.**
      Beide mitgelieferten Abläufe sprachen `RMBG` aus `ComfyUI-RMBG` an —
      GPL-3.0, nachgelesen in seiner Lizenzdatei. Solidon verlangte damit vom
      Kunden, eine GPL-Sammlung zu installieren, damit Weg 3 läuft. Der Verstoß
      hing an einer **Datendatei**, und deshalb hatte ihn keine Lizenzprüfung
      gesehen.

      ComfyUI kann es seit 0.33 selbst: `LoadBackgroundRemovalModel` und
      `RemoveBackground`, beide eingebaut, Gewichte BiRefNet unter MIT
      (`Comfy-Org/BiRefNet`, 444,5 MB). Damit fällt neben der Lizenzfrage ein
      Installationsschritt weg — es fehlt nur noch eine Datei. Der Ablauf wurde
      dabei sogar besser: TripoSG bekommt das Originalbild plus Maske statt
      eines weiß gefüllten Bildes. Ein älteres ComfyUI kennt die Knoten nicht,
      und dann nennt `missing_nodes()` sie mit Namen — das ist der richtige Weg
      dafür und keine zweite Version des Ablaufs.

- [x] **ComfyUI beschreibt Auswahllisten in zwei Formen, und wir lasen eine.**
      Klassisch steht die Liste als erstes Element (`[["TripoSG"], {…}]`); die
      neuen eingebauten Knoten schreiben `["COMBO", {"options": […]}]`. Beide
      kommen aus demselben Server — `TripoSGLoader` klassisch,
      `LoadBackgroundRemovalModel` neu. Wer nur die alte Form liest, hält jede
      neue Auswahl für leer und meldet „es fehlt die Modelldatei", obwohl sie
      daliegt. Genau das ist passiert, und jeder künftige eingebaute Knoten
      wird die neue Form haben.

### Das Zeitlimit galt der Grafikkarte, auf der es gemessen wurde

- [x] **Zehn Minuten waren an einer RTX 4080 gemessen, auf der ein Körper
      dreizehn Sekunden braucht.** Auf einer Intel-Arc-Grafik dauerte derselbe
      Lauf länger als das Limit: Solidon gab auf, ComfyUI rechnete weiter, und
      der Kunde hatte zehn Minuten gewartet und nichts. Das Limit gilt jetzt
      dem **Hängen** und nicht der Langsamkeit — solange der Auftrag in
      ComfyUIs Warteschlange steht, wird gewartet; `STUCK_SECONDS` deckelt auch
      das, damit ein ComfyUI, das seine Schlange falsch beantwortet, nicht
      endlos wartet.

- [x] **Der lokale Agent auf einem Rechner ohne nutzbare Karte: heute 51
      Minuten, bis eine Antwort beginnt.** Ollama spricht die Intel-Arc nicht
      an und rechnet auf dem Prozessor — `size_vram: 0.0`, 7,8 Token je Sekunde
      beim Einlesen. Der Systemprompt dieser Anwendung ist rund 24 000 Token
      lang. Die Anwendung sagte dazu nichts; sie sagte „Das Modell ruft
      Werkzeuge auf. Es ist brauchbar." Das ist wahr und nutzlos.

      Die Werkzeugprobe misst jetzt mit — ein Zug, der ohnehin läuft, und die
      Zahlen stehen in Ollamas Antwort. Sie nennt das Tempo, die Folge daraus
      und den einzigen Vorschlag, der hier trägt: einen Schlüssel für ein
      gehostetes Modell. Ein kleineres Modell rettet das nicht, und das steht
      ausdrücklich dabei. Die Geschwindigkeit **schlägt** die Werkzeugfrage:
      Wo eine Antwort einundfünfzig Minuten braucht, ist es unerheblich, ob das
      Modell Werkzeuge aufruft.

      **Nachgemessen am 28.08.2026:** Die ursprünglichen 41 Minuten gehörten
      zu 19 249 Token. Der heutige Produktionsauftrag mit Systemtext und allen
      106 kompakten Werkzeugen zählt bei `qwen3:14b` 23 891 Token; bei derselben
      gemessenen CPU-Rate sind das gerundet 51 Minuten. Ein Test bindet die
      Messung seitdem an die Werkzeugzahl.

### Der Auftrag war tot, und Solidon wartete zehn Minuten auf ihn

- [x] **ComfyUI beendet einen Auftrag mit `status_str: "error"`, und niemand las
      das.** Geprüft wurde nur, ob Ausgaben da sind — ein Auftrag, der nach
      Sekunden mit `execution_error` gescheitert war, sah genauso aus wie einer,
      der noch rechnet. Am Ende stand „Die Erzeugung hat ihr Zeitlimit
      erreicht", und der Grund hatte die ganze Zeit im Verlauf gestanden:
      „Torch not compiled with CUDA enabled", gemeldet vom Knoten mit Namen.

      Der Satz von ComfyUI reist jetzt mit, und zwar unübersetzt: Was dort
      steht, ist genauer als jede Umschreibung, und wer damit zum Support geht,
      bringt die Zeile mit, die weiterhilft. Der Knotenname steht davor — er
      sagt, in welchem Schritt es gerissen ist. Dieselbe Sache brauchte danach
      118 Sekunden statt 600, und die Auskunft war brauchbar.

- [x] **Und dieser Grund war der zwölfte Fund.** Der TripoSG-Quelltext setzt an
      sechs Stellen eine NVIDIA-Karte voraus, obwohl er keine bräuchte:
      `device='cuda'` hart eingetragen, viermal `torch.cuda.empty_cache()`,
      einmal `autocast(device_type="cuda")`. Unser eigener Knoten fragt ComfyUI
      nach dem Gerät (`get_torch_device`) und ist damit richtig; der geholte
      Quelltext fragt nicht. `patch_sources` flickte schon zwei Stellen in
      denselben Dateien — jetzt sind es diese drei Muster dazu.

      **Der erste Flicken hat die Datei zerbrochen, und das gehört
      aufgeschrieben.** Er hängte „# von Solidon" an die Zeile mit
      `torch.zeros`, und die ging weiter: `dtype` und `requires_grad` standen
      dahinter und waren wegkommentiert, die Klammer blieb offen. ComfyUI
      meldete „'(' was never closed", und die ganze Knotensammlung fiel aus.
      Gefangen hat es `nodes_load` — der Beleg dafür, dass dieser Schritt
      hingehört. Ein Test hält die Regel fest: Ein Kommentar am Zeilenende ist
      nur dort erlaubt, wo die Zeile auch endet.

### Und dann lief er

Ein Rendering von `clean_figure.stl` als Bild hinein, über unser eigenes
Backend an ein ComfyUI mit den eingerichteten Knoten. Heraus kam nach **119
Sekunden** ein `.glb` von 2,26 MB: **wasserdicht, eine Komponente** — genau
das, was der Modul-Docstring seit dem Wechsel auf TripoSG behauptet, und zum
ersten Mal nachgewiesen. Die Maße sind normalisiert (etwa 0,4 × 1,9 × 1,1), wie
TripoSG sie liefert; das Skalieren gehört auf den Stapel und nicht ins Backend
(§2.2, Weg 3).

Die Zahl ist die eines Rechners ohne CUDA-Karte. Der Docstring nennt daneben
weiter dreizehn Sekunden auf einer RTX 4080 — beide Zahlen gehören dahin, denn
sie sind der Abstand zwischen „das geht" und „das lohnt".

### Was auffiel und eine Entscheidung braucht

- [x] **Der lokale Weg ist auf Intel- und AMD-Grafik nicht praktikabel, und
      wir nennen keinen Ausweg.** Ollama unterstützt CUDA und Metal; auf allem
      anderen rechnet es auf dem Prozessor. Für Intel gibt es IPEX-LLM, für
      AMD ROCm-Versionen, für beides OpenVINO — jedes davon ist eine eigene
      Installation mit eigenen Fallen, und keines wird von Ollama selbst
      angeboten. Wartet auf eine Entscheidung, ob Solidon einen zweiten
      lokalen Weg **nennt** (nicht einrichtet) oder ob die Auskunft „hier lohnt
      es nicht, nimm einen Schlüssel" die ganze Antwort bleibt.

      **Entschieden am 26.08.2026 (Kundenmaßstab): nennen, ehrlich, abratend.**
      Die KI-Modelle-Seite trägt in allen sechs Sprachen eine Fußnote nach
      der TripoSG-Tabelle: NVIDIA gemessen, auf Intel/AMD rechnet der lokale
      Chat auf dem Prozessor (7,8 Token je Sekunde, 51 Minuten bis zur ersten
      Antwort), die Umwege heißen IPEX-LLM, ROCm und OpenVINO, werden weder
      mitgeliefert noch geprüft, und was trägt, ist ein Schlüssel — die
      Anwendung misst das seit dem 21.08. selbst und sagt es vor dem Warten.
      Eingerichtet wird weiterhin keiner der Umwege.

- [x] **Der Textweg prüfte seine Voraussetzungen nicht.** `readiness()` las
      `image_to_mesh.json`, und das war mit Absicht so: Der Bildweg ist der
      Kernweg, der Textweg braucht zusätzlich ein SDXL-Modell unter
      `models/checkpoints`. Wer keines hatte, erfuhr es beim Abschicken.

      **Gebaut, und zwar besser als die Frage lautete.** Der Punkt fragte, ob
      die Bereitschaft *zwei Stufen* bekommt — bereit für Bilder, bereit für
      Text. Stattdessen hängt sie jetzt am **gewählten Ablauf**:
      `readiness(workflow)` nimmt den Ablauf entgegen, und
      `GenerateDialog._workflow()` liefert ihn aus der Lage des Dialogs —
      `"image_to_mesh" if self._image is not None else "text_to_mesh"`. Der
      Docstring sagt, warum das die richtige Stelle ist: „Genau daran
      entscheidet `_run`, welchen der beiden Aufrufe es nimmt, und genau daran
      muss die Bereitschaftsfrage hängen."

      Geprüft wird dabei beides — die Knoten des Ablaufs (`missing_nodes`) und
      seine Modelle (`missing_models` → `Readiness.NO_MODEL`). Wer ohne Bild
      tippt, erfährt also vor dem Abschicken, dass das SDXL-Modell fehlt.
      Nachgeprüft am 22.08.2026 von 3d-druck-64 an `backends/mesh.py:395` und
      `ui/generate_dialog.py:161` und `:315`. **Neunter Registerpunkt, der beim
      Nachsehen schon gebaut war.**

## Der Schnapper griff nie, und der Absturz hat jetzt einen Stapel (22.08.2026)

Die zwei offenen Punkte des Durchgangs davor, beide angegangen. Einer ist
behoben, der andere ist von „passiert manchmal irgendwo" zu einer Zeilennummer
geworden.

### Behoben: der Schnappverbinder war unerreichbar

- [x] **Ein Werkzeug, das nie greift, ist schlimmer als keines.** Die Armlänge
      des Schnappers hing an der Länge des **Passstifts** — `1,5 mal Ø`, und
      der Durchmesser ist 12 Prozent der Nahtbreite (`PIN_RELATIVE`). Ein Arm
      braucht acht Millimeter, sonst federt er nicht (`SNAP_MIN_REACH`, und
      der Baustein rechnet daraus seine 0,8 mm Armstärke). Über diese Kette
      hätte eine Naht von **44 mm** hergehalten müssen. Gemessen an massiven
      Quadern:

      | Naht | Ø | Arm | Ergebnis |
      |---|---|---|---|
      | 23 auf 23 mm | 3,0 | 4,5 mm | runde Stifte, `split.snap_too_small` |
      | 40 auf 40 mm | 4,8 | 7,2 mm | runde Stifte, `split.snap_too_small` |
      | Sechskantstange 12 auf 22 | 3,0 | 4,5 mm | runde Stifte |

      Das ist die falsche Kopplung. Ein Passstift ist so tief eingebunden, wie
      er dick ist — eine Frage der Scherfestigkeit. Ein Federarm braucht
      Federweg, und den gibt das Material **hinter** der Naht, nicht das
      Stiftmaß. Der Durchmesser bleibt, wie er ist: Er begrenzt die Armstärke
      über den Umkreis, und bei Ø 3 kommen 0,88 mm heraus — mehr als die zwei
      Außenwände, die `SNAP_MIN_ARM` verlangt. Was fehlte, war allein die
      Länge.

      Alle drei Nähte tragen jetzt einen Schnapper mit 8 mm Arm; zurück auf
      runde Stifte geht es, wenn hinter der Naht keine acht Millimeter stehen
      (ein Quader von 12 mm Höhe, mittig geteilt, hat sechs). Der Befund nennt
      jetzt die **Tiefe** — vorher nannte er den Stiftdurchmesser und damit die
      Größe, die mit der Sache nichts zu tun hat.

      Durch den Kundenweg gefahren: Die massive Säule des 52-teiligen Bausatzes
      (23 auf 71 auf 23) kommt als Paar „A · Stifte" und „B · Löcher" heraus,
      beide geschlossen, ohne Befund, exportiert und zurückgelesen. Die Basis
      daneben bleibt bei runden Stiften und meldet `split.face_too_small` —
      richtig, denn sie ist ein Rahmen, und ihre Schnittfläche sind dünne
      Stege.

### Der Absturz: eine Zeilennummer statt einer Vermutung

Gefangen mit `tools/qt_trace.py` — einer pytest-Erweiterung, die Qts Meldungen
und die Kennung jedes Tests sofort in eine Datei schreibt. Beides ging vorher
verloren: Eine Zugriffsverletzung reißt den Prozess ab, ohne seine Puffer zu
leeren.

Im ersten Lauf über die zweite Hälfte der Suite schnappte sie zu, und
`faulthandler` gab den Stapel dazu:

```
app/ui/session.py:110   _EvaluationWorker.__init__   (super().__init__() — ein QThread entsteht)
app/ui/session.py:1029  evaluate_async
app/ui/session.py:1363  _on_thread_done              (der finished-Slot des Vorgängers)
app/ui/session.py:1394  wait_for_idle
tests/test_ui.py:448    test_the_panels_follow_the_evaluation
```

Damit steht die Stelle: **Der Nachfolge-Arbeiter entsteht im
``finished``-Slot seines Vorgängers**, über den `_rerun_pending`-Zweig. Die
Gebietsregel sagt über dieselbe Stelle „``finished`` heißt ‚``run`` ist
zurück', nicht ‚das Objekt darf weg'" — einen neuen `QThread` in genau diesem
Moment zu bauen ist derselbe Griff, einen Schritt weiter.

Keine Qt-Meldung davor: Es ist eine Zugriffsverletzung und kein `qFatal`, also
**nicht** „QThread: Destroyed while thread is still running". Eine
Zugriffsverletzung in einer nackten `QThread`-Konstruktion deutet auf einen
Schaden, der vorher entstanden ist und hier bloß auffällt.

- [x] **Was fehlt, ist der Beweis, nicht die Vermutung.** Nicht reproduzierbar:
      derselbe Dateisatz in derselben Reihenfolge lief beim zweiten Mal
      durch, und zwölf Läufe der Einzeletappe mit Instrumentierung blieben
      sauber. Damit wäre jede Änderung an der Auswertung geraten — und die
      naheliegende (den Neustart um einen Durchlauf der Ereignisschlange
      verschieben) greift in `wait_for_idle` ein, das genau darauf baut, dass
      `_worker` beim Verlassen des Slots wieder besetzt ist. Ein Hänger dort
      wäre schlimmer als ein seltener Absturz. Der Weg bleibt ein Lauf unter
      einem Werkzeug, das doppelte Freigaben sieht; die Falle steht jetzt
      dafür bereit.

      **Aufgegangen in Signatur B** (23.08.2026, sortiert an 24 Stapeln):
      Die Stelle `session.py:110` liegt **zwei Zeilen** neben
      `session.py:112`, die in neun der 24 Stapel steht. Der Beweis, der hier
      fehlte, ist die Konstellation im Hauptpunkt.

      **Nachtrag vom selben Abend: der zweite Stapel, und er widerlegt die
      Verengung.** Der geteilte Lauf fing ihn in `tests/test_ui.py` — dieselbe
      Absturzstelle, ein anderer Weg dorthin:

      ```
      app/ui/session.py:110    _EvaluationWorker.__init__   (wie beim ersten Mal)
      app/ui/session.py:1029   evaluate_async               (wie beim ersten Mal)
      app/ui/session.py:472    _reset_for                   <- neu
      app/ui/session.py:414    start_new                    <- neu
      app/ui/main_window.py:2549  open_path                 <- neu
      tests/test_ui.py:3176    test_the_wired_dialog_previews_into_the_viewport
      ```

      Kein `finished`-Slot, kein `wait_for_idle`, kein Ablösen eines laufenden
      Arbeiters — ein schlichtes Öffnen einer Datei. Damit ist die Erklärung
      von oben („der Nachfolge-Arbeiter entsteht im `finished`-Slot seines
      Vorgängers") **nicht** die Ursache, sondern war ein zweiter Ort, an dem
      derselbe Schaden auffiel. Der Satz daneben stimmt dafür umso mehr: „Eine
      Zugriffsverletzung in einer nackten `QThread`-Konstruktion deutet auf
      einen Schaden, der vorher entstanden ist und hier bloß auffällt."

      Das ist gut für die Suche: Was zu prüfen ist, liegt **vor**
      `_EvaluationWorker.__init__` und nicht in den Aufrufern. Der Fix von
      damals bleibt richtig, er war nur nicht der ganze Fund.

## Vierzig Prozent der Ansicht sieht das Tor nie (22.08.2026)

Aus der Messung zu „erstnutzer 4.1" entstanden, und der Anlass ist kleiner als
der Befund. Die Frage war, ob die Druckplatte nach einem Themenwechsel hell
wird. Die Antwort ist: **Das kann kein Test sagen, weil die Methode, die die
Platte zeichnet, in der Suite kein einziges Mal läuft.**

### Was schon bekannt war, und was neu ist

`.claude/rules/oberflaeche.md` kennt die Sache an drei Stellen und benennt sie
scharf: „Offscreen gibt es keinen Plotter, und jeder Setzpfad steigt vorher
aus", und „ein Test, der sich dort überspringt, prüft nie etwas." Das Mittel
dagegen steht auch dort — eine Attrappe mit genau der einen benutzten Methode,
wie in `tests/test_cursors.py`; `tests/test_analysis_ui.py` setzt an neun
Stellen einen Plotter ein.

**Neu ist allein die Größe.** Die stand nirgends, und sie ist der Grund, warum
aus einer bekannten Einschränkung eine offene Frage wird.

### Gemessen

`_available()` gibt auf der Offscreen-Plattform ausdrücklich `False` zurück —
„VTK braucht einen echten OpenGL-Kontext; auf der Offscreen-Qt-Plattform
scheiterte es nicht höflich, sondern nähme den Prozess mit." Damit ist
`self.plotter` in der ganzen Suite `None`, außer wo ein Test eine Attrappe
einsetzt.

```
Viewport                             134 Methoden, 2747 Zeilen
davon hinter `plotter is None`        40 Methoden, 1108 Zeilen   (40 %)
```

Gefahren über **23 Fensterdateien mit 1597 Tests** (die drei, die beim Abbau
abstürzen, fehlen — sonst schreibt das Protokoll nicht):

```
kommen nie hinter die Wache           30 Methoden,  497 Zeilen
kommen dahinter (über eine Attrappe)  10 Methoden
```

**Alle vierzig werden aufgerufen. Bei dreißig läuft der Rumpf nie.** Die
größten:

| Zeilen | Methode |
|---|---|
| 79 | `_draw_one_bed` — die Druckplatte |
| 53 | `_redraw_features` |
| 41 | `_redraw_feature_patch` |
| 31 | `_add_orientation_widget` |
| 31 | `_redraw_measurements` |
| 29 | `_redraw_layer` |
| 25 | `_draw_feature_edges` |
| 20 | `_draw_brush` |

Gemessen ohne neue Abhängigkeit: `coverage` ist nicht installiert, und es dafür
einzubauen wäre ein Eintrag in der Lizenzliste für eine einmalige Frage. Ein
Zeilenschreiber über `sys.settrace`, der nur `app/ui/viewport.py` mitschreibt,
tut dasselbe in dreißig Zeilen.

### Warum das 4.1 entscheidet, ohne es zu beantworten

`_draw_one_bed` ist der größte nie ausgeführte Rumpf. Ein Test, der den
Themenwechsel prüft, erreicht die vier Zuweisungen in `set_theme` und kehrt
danach um; was die Ansicht *zeichnet*, sieht er nicht. Deshalb blieb 4.1 auch
nach einer Messung am echten Bildschirm offen — und deshalb ist ein Test dafür
schlimmer als keiner: Er wäre grün und würde die Lücke zudecken.

- [x] **Von dreißig Rümpfen sind fünf ungeprüft — alle fünf geschlossen am
      23.08.2026** (`deb3138` und davor). Nachgemessen: **null** Rümpfe, die
      weder über ihren Namen noch über einen Helfer erreicht werden.

      Die letzten drei betrafen den Fall, den diese Maschine nie zeigt — einen
      Treiber, der weniger kann: Kantenglättung und Verdeckung im `try`
      (einfacheres Bild statt Absturz), der `return` im Fehlerpfad der
      Verdeckung (ohne ihn verbucht ein einmaliger Treiberfehler dauerhaft
      „ist an", und der Viewport probiert es nie wieder), und der Kamera-
      Beobachter, der schwach hält. Jeder mit Gegenprobe, `viewport.py`
      danach wieder identisch mit HEAD.

      **Die Vorbehalt-Zeile gilt weiter:** „Name kommt in einer Testdatei vor"
      ist schwächer als „Rumpf wird gefahren".

      Ursprünglich:
      Gemessen am 23.08.2026 (3d-druck-b8), indem je Methode gefragt wurde, ob
      ihr Name **oder einer ihrer Helfer** überhaupt in einer Testdatei
      vorkommt:

          Methoden mit Offscreen-Wache            35
          davon weder Name noch Helfer in Tests    5
          davon am 23.08. geschlossen              3

      **Der Unterschied zu „dreißig" kommt aus der Reihenfolge, die der Punkt
      selbst vorgibt** — *erst prüfen, ob sich die Aussage vor die Wache ziehen
      lässt*. Das ist bei den meisten längst geschehen: `rotation_centre` und
      `gizmo_labels` sind eigene Funktionen mit eigenen Tests, und was hinter
      der Wache bleibt, ist reines Zeichnen. `_draw_one_bed`, der größte von
      allen, ist über die Attrappe geprüft.

      **Geschlossen wurden die, bei denen das nicht ging:**

          e6b01b0  _redraw_features        ohne Überlagerung bleibt das
                                           gewählte Merkmal beschriftet (Regel 18)
          271caea  _redraw_feature_patch   die Dreiecke des Merkmals, nicht die
                                           des Körpers, plus Versatz
          475eb82  _draw_feature_edges     eine Kugel bekommt keine Kanten
          3fca3ed  _note_pointer           Qt zählt von oben, VTK von unten
          3fca3ed  set_projection          orthografisch erreicht den Plotter

      **Die Zahl ist eine Untergrenze und nicht die Wahrheit** — „der Name
      kommt in einer Testdatei vor" heißt nicht „der Rumpf wird gefahren". Ein
      Test kann `set_navigation` erwähnen und offscreen trotzdem an der Wache
      abbiegen. Der Vorbehalt gehört zur Zahl.

      **Offen sind `_watch_camera` (20 Zeilen), `_apply_render_quality` (20)
      und `_apply_ambient_occlusion` (13).**

      **Und ein Fund am Prüfwerkzeug selbst, der die Leitfrage weiterdreht:**
      Beim Kugel-Test blieb die erste Gegenprobe wirkungslos, und das sah aus,
      als sei der Test schwach. Nachgemessen war die **Probe** schlecht
      gewählt — VTK liefert dort auch mit dem geänderten Schalter null Kanten;
      der Schalter, der wirkt, ist der Winkel.

      > Eine wirkungslose Gegenprobe beweist nichts, weder für den Test noch
      > gegen ihn.

      Der ursprüngliche Text:

      **Welche eine Attrappe verdienen** — nicht alle: Eine Attrappe
      je Methode ist Arbeit, und für manche wäre sie eine Nachbildung von VTK.
      Der Vorschlag wäre, bei den vier größten anzufangen, die etwas *zeigen*,
      was der Nutzer beschreibt — Platte, Merkmale, Maße, Schichtansicht — und
      die restlichen ausdrücklich als „nicht geprüft" zu führen, statt sie
      stillschweigend mitlaufen zu lassen. Das ist eine Entscheidung und keine
      Aufgabe; die Zahl steht jetzt dabei.

      **Nachtrag vom selben Tag: die Frage war falsch herum gestellt.**
      `solidon-b0` hat beim Umbau der Viewport-Auswahl gezeigt, dass ein Teil
      der dreißig nicht dort steht, weil das Entscheiden VTK bräuchte, sondern
      weil **Entscheiden und Zeichnen in derselben Methode wohnen**.
      Herausgezogen sind jetzt `_click_target`, `_feature_at`,
      `selection_depth` und `_select_at` — reine Aussagen über die Szene, ohne
      Plotter-Wache. Sechzehn von achtzehn Tests wurden in der Gegenprobe gegen
      HEAD rot; ohne diese Zahl wäre es eine schöne Idee geblieben.

      Damit lautet die Reihenfolge: **erst herausziehen, dann erst eine
      Attrappe.** Eine Attrappe prüft, dass der Aufruf ankommt; eine
      herausgezogene Entscheidung prüft, dass sie stimmt. Das Zweite ist mehr
      wert und altert besser.

      Eine Attrappe bleibt nötig, wo die Methode wirklich VTK braucht.
      `_look_under_pointer` (21 Z) ist so erreicht worden
      (`tests/test_selection.py::test_the_resting_pointer_reaches_the_decision`,
      Attrappe für `renderer` und `interactor`, Monkeypatch auf `_world_under`).
      `_world_at` und `_face_handle` sind es ausdrücklich **nicht** — sie
      brauchen einen echten Picker. Diese zwei Negativbefunde sind der
      nützlichste Teil: Sie sagen, wo die Grenze der Methode liegt.

      Der Bauplan hat die Reihenfolge übernommen (§35): Ein Test hinter einer
      Wache, die nie fällt, ist grün und prüft nichts — die Antwort darauf ist
      nicht die nächste Attrappe, sondern die prüfbare Aussage aus dem
      Unprüfbaren herauszulösen.

## Das Fundament der Wahrnehmung (22.08.2026)

Roberts Auftrag war „alles Grundlegende zur App kontrollieren, optimieren,
recherchieren, ausarbeiten". Vier Sitzungen haben daran gearbeitet; was hier
steht, ist der Rest, der offen blieb, und der Grund, warum er es ist. Was
behoben wurde, steht in den Commits und im Bauplan — und die Funde hatten
untereinander eine Form: **Die Kette hängt am Namen, nicht am Inhalt.**

Drei Fälle, an einem Tag, aus drei verschiedenen Ecken:

* Ein erzeugtes Merkmal verlor seinen Namen an eine Operation, die ihr Feld
  leer ließ — lautlos, ohne Befund (behoben, `b76df19`).
* Eine gesenkte Bohrung verlor die **ganze** Bohrung, weil Kegelwand und
  Bohrungswand ein Fleck waren (behoben, `db4a820`).
* Ein eigener Baustein, dessen Maß der Nutzer ändert, behält Name und
  Parameter — der Operations-Hash sieht nichts, und auf der Platte überlebt das
  Ergebnis (siehe unten).

- [ ] **Der Verweisfilter schlüsselt nach Objekt-Kennungen, die im Stapel
      wechseln.** `referenced_features` in `evaluate` entsteht einmal je
      Auswertung und hängt Merkmale an die Objekt-ID aus dem Dokument — aber
      Kennungen entstehen und wechseln über den Stapel hinweg, und ein
      Verweis auf `obj_2` erreicht die Mehrdeutigkeitsfrage von `obj_2`
      nur, solange die Kennung beim Verweiszeitpunkt dieselbe ist wie beim
      Aufbau (Fund 16 des Update-Reviews, 26.08.2026 — die andere Hälfte,
      die Skizzenebenen, ist seither über die „irgendwo"-Menge abgedeckt).
      Eine ehrliche Lösung braucht Objektidentität über den Stapel, nicht
      einen breiteren Schlüssel: Alles in die „irgendwo"-Menge zu heben
      stellte genau die Fragenflut wieder her, die §15.7 begraben hat —
      `hole_1` gibt es an jedem Körper mit Löchern.

- [ ] **Die Antwort der Zuordnung steht nirgends — die Mechanik steht, die
      Abnahme fehlt.** Gebaut am 23.08.2026 (`67b0386`): `Operation.matches`
      trägt die Antwort, `serialise` schreibt und liest sie, `_with_features`
      fragt erst den Stapel und dann den Nutzer. Zwei Einheitstests decken es
      (`test_the_question_of_the_matcher_is_asked_once_and_then_never_again`
      und der Weg über die neu geöffnete Datei).

      **Die Abnahmezahl ließ sich nicht messen, und der Grund ist der
      eigentliche Fund.** Gemessen wurde über `evaluate` — dort entstehen die
      Fenster, nicht in `match`:

          eingelesene Zwillingsplatte + compensate_first_layer + 5 Schritte
              erster Lauf   0 Fenster        zweiter Lauf   0 Fenster
          erzeugte Bohrungen (drill_hole) + 5 Schritte
              erster Lauf   0 Fenster        zweiter Lauf   0 Fenster

      **Beide Male ist null die richtige Antwort, und beide Male aus demselben
      Grund:** Die Bohrungen stehen von Anfang an alle da, und jede findet bei
      der nächsten Auswertung ihre eigene wieder. Eine kleine Verschiebung
      ändert daran nichts.

      *Hier stand zuerst eine zweite Erklärung für die gebohrten — sie kennten
      seit `created_by` ihre Herkunft. Das ist falsch, nachgewiesen von
      3d-druck-b8:* `created_by` wird nur für `provenance="generated"` gesetzt,
      und das gibt es an genau zwei Stellen (`knowledge/parts/build.py` und
      `geom/pins.py`). `drill_hole` deklariert nichts — was es hinterlässt,
      findet die Erkennung wieder, und ein erkanntes Merkmal ist `detected`.
      Die falsche Erklärung war dabei nicht nur falsch, sondern **überflüssig**:
      Sie erfand einen Sonderfall für etwas, das die allgemeine Regel schon
      abdeckt.

      **Die dritte Zahl ist die aufschlussreiche, und 3d-druck-3a hat sie
      gemessen statt vermutet.**
      `test_an_ambiguous_match_stops_with_a_finding_instead_of_escaping` ist
      rot, und der Grund liegt im Testkörper: Der hohle Quader dort hat
      **überhaupt keine Bohrung**. Was die Erkennung als zwei meldete, sind
      seine verrundeten Innenkanten — zwei Flecken mit r = 1,99, gleiche Achse,
      gleicher Durchmesser, für `feature_vector` ununterscheidbar bis auf die
      Position. Genau daran hing die geprüfte Mehrdeutigkeit.

          ohne die Krümmungszusammenfassung   2 "Bohrungen"   complete = False
          mit  der Krümmungszusammenfassung   4 "Bohrungen"   complete = True

      Die vier waren immer da; der Abbruch bei der Mehrdeutigkeit verdeckte die
      anderen zwei. `match` selbst ist intakt — 26 grüne Tests, darunter der
      Zwillingsfall.

      **Damit ist der Satz über den Punkt hinaus brauchbar: Der Test prüft eine
      Zusicherung des Fehlerpfads über einen Zufall.** Die Zusicherung ist gut
      und gilt weiter — eine `AmbiguityError` muss ein Befund werden statt einer
      Ausnahme, sonst bekommt jeder ohne Frage-Dialog (Kommandozeile,
      Fernsteuerung, Agent) eine Ausnahme und einen leeren Prüfbericht.
      Gebraucht wird dafür *irgendeine* Mehrdeutigkeit; benutzt werden zwei
      **Fehlbefunde** an einem Körper ohne Bohrungen. Jede Verbesserung der
      Erkennung kippt so einen Test, und zwar zu Recht.

      **Der naheliegende Ersatz funktioniert nicht — auch das ist gemessen.**
      Zwei echte gleichwertige Bohrungen (`plate_holes_twin.stl`) stellen über
      den Stapel keine Frage: Zwillinge, die beide von Anfang an dastehen,
      bleiben jeder bei sich. Zwei gespiegelte `drill_hole` ebenso wenig, weil
      erzeugte Merkmale seit `created_by` ihre Herkunft kennen. Mehrdeutigkeit
      entsteht erst, wenn ein **altes** Merkmal auf **zwei neue** gleich gut
      passt — die Merkmalszahl muss sich ändern, so wie in
      `test_two_identical_bores_close_together_are_ambiguous` (eine Bohrung
      wird zu zweien).

      Der ursprüngliche Text, weil seine Begründung weiter gilt:

      **(Ursprünglich, 22.08.2026)** Bauplan §15.7 hat am
      22.08.2026 entschieden, wohin eine Antwort gehört, und die **erste
      Hälfte ist gebaut** (`311134a`): Was eine Operation selbst erfragt — die
      Einheit in `load` — gibt sie zurück, der Verlauf schreibt es in ihre
      Parameter, die zweite Auswertung fragt nicht mehr.

      **Offen ist die zweite Hälfte, und sie ist die teurere.** Welches neu
      erkannte Merkmal einen alten Namen erbt (§21.3), ist keine Eingabe der
      Operation — es passt in keinen Parameter, und die Schemaprüfung würde
      einen erfundenen Schlüssel abweisen. Es braucht ein Feld an der
      Operation neben `solver` und `seed` und damit eine Formatänderung.
      Entwurf, Begründung, die drei Einwände dagegen und die eine noch offene
      Frage (Abdruck absolut oder normiert) liegen in
      `.claude/memory/merkmalsmehrdeutigkeit-entwurf.md` — wer dort aufnimmt,
      fängt beim Bauen an und nicht beim Denken.

      **Die Abnahme ist eine Zahl:** Über die ganze Kette stellte eine
      Bauplatte mit 52 Teilen **99 modale Fenster für 7 Entscheidungen** —
      sechzehnmal „Welches Merkmal entspricht `pin_1`?", sechzehnmal `pin_2`.
      99 muss 7 werden, und beim zweiten Auswerten 0.

      Dazu eine Prüfung, die nichts über Innereien wissen muss: Der Wächter aus
      `342a32c` hält ein Ergebnis, für das gefragt wurde, aus dem Plattencache
      heraus, und er wickelt **beide** Fragesteller ein — die Operation und die
      Zuordnung. Greift er für die Zuordnung nie mehr, ist keine Antwort mehr
      unaufgeschrieben. Das ist der Beweis, dass §15.7 vollständig ist, und er
      ist besser als „die Antwort steht im Stapel".
- [x] **Ein geänderter eigener Baustein wird beim Öffnen nicht gemeldet —
      erledigt, geprüft am 23.08.2026.** `changed_own_parts` in
      `parts/check.py` vergleicht je benutztem Baustein einen Abdruck seiner
      Datei; `stamp()` schreibt ihn beim Speichern und räumt dabei die Abdrücke
      von Bausteinen weg, die das Projekt nicht mehr benutzt. Der Befund
      `parts.own_changed` hängt in `check()` und kommt über
      `app/ui/session.py:133` beim Öffnen an. Fünf Zusicherungen in
      `test_parts_catalog.py` decken ihn ab.

      **Zwei Entscheidungen darin sind es wert, hier zu stehen.** Erstens
      schweigt ein *fehlender* Abdruck: Projekte von vor dieser Änderung haben
      keinen, und eine Datei, die sich nicht lesen lässt, auch nicht — beides
      heißt „keine Aussage möglich". Ein Falschbefund bei jedem alten Projekt
      wäre schlimmer als die Lücke, die er schließt. Zweitens fallen Abdrücke
      unbenutzter Bausteine beim Speichern weg, weil ein Schlüssel, den niemand
      mehr liest, sonst mit jedem Speichern älter wird und irgendwann wie eine
      Aussage aussieht.

      Ursprünglich stand hier: §24.4 verspricht einen Hinweis, welche *benutzten* Bausteine sich seither
      geändert haben. `changed_since_library` löst das über die gepflegten
      Änderungsverläufe eines Bausteins — richtig für alles, was mit einer
      Auslieferung kommt. Ein eigener Baustein aus `<Nutzerdaten>/parts/*.py`
      (§24.5) hat keinen Änderungsverlauf: Der Nutzer ändert ein Maß und
      speichert. Damit gibt es für ihn keine Warnung, unabhängig von jedem
      Cache. Gefunden von solidon-17, deren Cache-Schranke denselben Fall über
      Name, Änderungszeit und Größe der Dateien löst — dieselbe Auskunft, die
      auch die Warnung bräuchte.
- [x] **Eine gesenkte Bohrung galt als Sackloch.** `_is_through` verglich die
      Tiefe der Zylinderwand mit der Dicke des Körpers entlang der Achse. Bei
      `plate_countersunk.stl` sind das 5,6 gegen 8 mm, weil die Senkung die
      oberen 2,4 mm übernimmt — die Auskunft ist über den Zylinder richtig und
      über das Teil falsch, und eine Schraube geht durch. Solange der Kegel
      kein Merkmal war, ließ es sich nicht entscheiden; seit dem 22.08. schon:
      Eine Bohrung ist durchgehend, wenn Bohrung **und** koaxialer Kegel
      zusammen die Dicke überspannen. Der Test hält den heutigen Stand
      ausdrücklich als Zylindertiefe fest und behauptet nichts über „durch".
      **Behoben am 22.08.2026 (`770f1b1`).** `_is_through` mass die Höhe der
      Zylinderwand gegen die Dicke des Körpers; bei einer Senkung gehört das
      obere Stück des Lochs zum Kegel, an einem gesenkten M5-Durchgangsloch in
      8 mm also 5,6 gegen 8. Nicht nur Anzeige: Eine Passung sucht ihr
      Gegenstück über die Merkmalsart (§14). Gerechnet wird jetzt über die
      **Vereinigung** der Achsabschnitte von Bohrung und zugehöriger Senkung —
      Überlappung zählt einmal. `_sinks_into` entscheidet die Zugehörigkeit über
      `recess`, Achsparallelität auf den Betrag, Kegelradius und Konzentrizität,
      dazu eine Anschlussprüfung gegen den Fall zweier koaxialer Bohrungen durch
      zwei Wände. Die neue Korpusdatei `plate_countersunk_blind.stl` (gesenkte
      **Sack**bohrung, 3,6 + 2,4 von 8 mm) hält fest, dass eine Senkung allein
      noch kein Durchgang ist — ohne sie wäre jede falsche Lösung grün gewesen.
      Bauplan §9 und §42 am selben Tag nachgezogen (`0c90a3a`): `Feature.kind`
      führt `"cone"`, und §42 nennt den Kegel nicht mehr unter dem, was fehlt.
      Gebaut von 3d-druck-3a.

- [x] **Eine erkannte Verrundung lässt sich nicht ändern** — auf dem **exakten**
      Körper gelöst, über `BRepAlgoAPI_Defeaturing`: R3 → entrundet → R5, Volumen
      23845,5 → 24000,0 (scharfer Quader), und der harte Fall mit 20 Flächen an
      Dreifach-Ecken geht exakt auf. **Der Mesh-Teil bleibt offen** und ist der
      Punkt darunter.

      Ursprünglich: Sobald `fillet`
      eine eigene Merkmalsart ist (3d-druck-3a, 23.08.2026), hat sie ein
      Kontextmenü — und darin steht nichts, was ein Kunde will.

      **`fillet_edges` ist nicht die Antwort, obwohl es die naheliegende
      wäre.** Die Operation verrundet **Kanten**, und eine Verrundung ist
      keine Kante, sondern ihr Ergebnis: Wer eine bestehende Rundung anklickt
      und „Verrunden" wählt, verrundet die Rundung. Was er will, ist **den
      Radius ändern**, und diese Operation gibt es nicht. Sie zu erfinden,
      damit eine Prüfung grün wird, wäre die Reihenfolge verkehrt — dasselbe
      Argument, mit dem `sphere` und `torus` in `known_gaps` liegen, statt
      eine angedichtete Operation zu bekommen. Der Eintrag dort muss das
      deshalb **sagen**: nicht „keine Operation vorhanden", sondern „die
      passende wäre *Verrundungsradius ändern*; *Verrunden* wirkt auf Kanten
      und ist nicht dasselbe". Sonst liest der Nächste, es fehle nichts.

      **Der zweite Weg fällt ebenfalls aus, und das ist der weniger
      offensichtliche Teil.** Seit `64769bc` bietet ein Merkmal „Diesen
      Schritt ändern" an — aber nur, wenn es einen Erzeuger hat, und
      `created_by` wird ausschließlich für `provenance="generated"` gesetzt.
      Das gibt es an zwei Stellen: Bausteine und Verstiften. **Auch eine
      selbst gesetzte Verrundung ist damit `detected`** und trägt keinen
      Schritt. Der Punkt betrifft also nicht nur eingelesene Modelle, wie es
      zuerst aussieht, sondern jede Verrundung.

      **Gemessen am 23.08.2026, und der Punkt ist so nicht lösbar** — er baut
      auf einer Voraussetzung auf, die es nicht gibt (3d-druck-3a):

          create_box + fillet_edges  ->  complete: False
              op.fillet_edges.NeedsSolidError
              „Der gewählte Körper ist ein Netz."

      **Verrunden geht auf einem Netz nicht, und der Kundenfall ist der
      Netzfall** — „eine heruntergeladene Verrundung" heißt STL heißt Netz.
      Eine Operation *Verrundungsradius ändern* hätte dieselbe Schranke und
      hielte bei jedem dieser Modelle an. Im anderen Fall braucht es sie
      nicht: Bei einem exakten Körper, den Solidon selbst gebaut hat, greift
      „Diesen Schritt ändern" über die Provenienz, und der Radius steht in den
      Parametern des Erzeugerschritts. **Der Punkt hängt damit am B-Rep-Kern
      für eingelesene Geometrie** und nicht an einer Operation.

      **Und für den dritten Fall — einen eingelesenen *exakten* Körper — ist
      die Antwort besser als die Frage.** Auf einem B-Rep-Körper läuft `detect`
      gar nicht; es gibt eine eigene Erkennung (`brep/features.py`), und die
      passt nichts ein, sondern **liest aus der Topologie**. Gemessen an einem
      exakten Quader mit R3 an vier senkrechten Kanten:

          features_of                6 Merkmale, alle 'face'
          in der Topologie           Zylinderfläche r = 3.000 mm,
                                     Umdrehung 0.250   (viermal)

      **Der Radius steht exakt da** — kein Einpassen, keine Streuung, keine
      Schwelle. Verworfen werden die vier von `FULL_TURN = 0.9`, dessen
      Kommentar die Merkmalsart selbst benennt: *„Darunter ist sie eine
      Verrundung oder eine gerundete Ecke, kein Loch."*

      Bemerkenswert dabei: Die Netz-Messung (Verrundung 90°, Zapfen 345°) und
      `FULL_TURN` ziehen **dieselbe** Trennlinie — 0,25 gegen 0,9. Zwei Kerne,
      zwei Wege, eine Grenze; das spricht dafür, dass sie in der Sache liegt
      und nicht in der Methode.

      **Auf dem B-Rep-Kern lässt sie sich ändern — gemessen am 23.08.2026
      (3d-druck-3a), und der Punkt sagt damit nicht mehr „geht nicht", sondern
      „so geht es".** OCCT bringt `BRepAlgoAPI_Defeaturing` mit:

          R3 (Ausgang)      4 Verrundungen, Radius 3,0
          entrundet         0 Verrundungen
          R5 (neu)          4 Verrundungen, Radius 5,0

          Volumen verrundet    23845,5
          Volumen entrundet    24000,0
          scharfer Quader      24000,0     <- auf die Stelle

      **Es ist kein Zurückrechnen und kein Annähern:** Defeaturing nimmt die
      Fläche heraus und verlängert die Nachbarflächen bis zum Schnitt. Danach
      ist die Kante wieder da, und `edit.fillet` setzt einen neuen Radius
      darauf. Auch der harte Fall trägt — an einem Quader mit Verrundungen an
      **allen** Kanten (20 Flächen, 12 Zylinder und 8 Kugeln) geht es exakt
      auf: 23701,7 → 24000,0.

      **Möglich wurde das erst in derselben Nacht:** Bis dahin wusste der
      B-Rep-Kern nicht, welche Fläche eine Verrundung ist — er warf sie über
      `FULL_TURN` weg. Seit `fillet` dort eine Merkmalsart ist, trägt jede
      Verrundung ihre `face_indices`, und genau die braucht Defeaturing als
      Eingabe.

      **Offen bleibt der Mesh-Fall, und der ist der Kundenfall.** Wer ein STL
      einliest, hat keinen exakten Körper; `fillet_edges` scheitert dort
      weiterhin mit `NeedsSolidError`. Der Punkt hängt damit unverändert am
      B-Rep-Kern für eingelesene Geometrie — nur ist jetzt belegt, dass es
      **dahinter** einen Weg gibt und nicht nur eine Hoffnung.

      **Zu entscheiden ist damit eine Frage, die größer ist als dieser
      Punkt:** Soll eine Operation, die ein Merkmal *sichtbar* hervorbringt,
      es auch **deklarieren** — oder bleibt die Provenienz den beiden
      heutigen Erzeugern vorbehalten? Für „deklarieren" spricht, dass der
      Rückweg vom Ergebnis zum Schritt dann überall funktioniert und nicht
      nur an Bausteinen. Dagegen spricht, dass jede der fünfzehn Operationen
      mit `features={}` dann eine Entscheidung braucht, welche ihrer
      Ergebnisse sie beansprucht — und eine falsche Beanspruchung ist
      schlimmer als keine, weil der Klick dann in den falschen Dialog führt.

- [x] **Ein Verrundungsradius ist nicht abzulesen** — gebaut (`e3b01b7`, `eb1a541`). `block_with_rounded_edge.stl` liefert `[('fillet', 2.999)]`, und die Krümmungskarte gibt 50 Werte in Millimetern (3,00 bis 568,34) statt einer Färbung.

      Ursprünglich: Die Krümmungskarte aus
      §18.4 färbt, was rund ist, und sagt nicht, *wie* rund — der Radius einer
      Verrundung steht nirgends. Er steht im Torusstück, das sie erzeugt, und
      dafür muss der Torus ein Merkmal sein. Damit ist dieser Punkt der
      eigentliche Gewinn der Kugel-und-Torus-Erkennung (§41) und nicht ihr
      Nebenprodukt: Wer eine heruntergeladene Verrundung nachbauen oder
      angleichen will, braucht die Zahl und nicht die Farbe.
- [x] **Die Zuordnung kennt Kugel und Torus nicht — geprüft und erledigt am
      23.08.2026 (`9cedb94`, 3d-druck-3a), und die Kostenmatrix brauchte
      nichts.** `feature_vector` liest artenunabhängig; was fehlte, war ein
      **Parametername**. `ring_diameter` machte zwei Ringe mit Ø 40 und Ø 60
      ununterscheidbar — Kosten 0,0, also derselbe Ring. Heute heißt der
      Schlüssel `diameter`, und sie kosten 2,22.

      **Der Fall gehört neben `ring_diameter` als Beschriftung**: Eine
      Zeichenkette, die aussieht wie ein Anzeigename und in Wahrheit ein
      Vertrag ist. Wer sie umbenennt, ändert die Zuordnung; wer sie liest,
      sieht ein Etikett.

      Ursprünglich: Die Kostenmatrix aus §21.2
      führt die Merkmalsarten einzeln; zwei neue Arten, die erkannt werden,
      aber in der Zuordnung fehlen, sind ein halber Zustand — sie tauchen im
      Baum auf und finden über eine Auswertung hinweg kein Gegenstück. Dazu
      gehören ihre Namen in der Oberfläche, in allen fünf Katalogen.

      Beim Schneiden des Auftrags für Kugel und Torus zunächst abgeschnitten
      (3d-druck-64), und das war die falsche Grenze: Dieselbe Konsistenzfrage
      wie bei den Übersetzungen, die bewusst dazugenommen wurden. Acht Arten,
      die überall gleich auftauchen, schlagen zehn, die auseinanderdriften.
- [x] **Kugel und Torus fehlen der Erkennung** — gebaut (`9cedb94`, Torusausschnitte `fda888d`). Nachgemessen: `sphere_socket.stl` → `sphere`, `torus_ring.stl` → `torus`.

      Ursprünglich: Vier Arten waren es, fünf sind
      es: `hole`, `pin`, `face`, `edge_loop`, `cone`. Was fehlt, ist die Kugel
      (Pfanne, Kalotte) und der Torus — und mit dem Torus fehlt der **Radius
      einer Verrundung**. Der Weg steht als Ausbaustufe in Bauplan §41, mit dem
      Preis daneben: Ein Anpassungsverfahren, das Grundformen sucht, findet
      auch welche, die niemand gemeint hat, also braucht es eine eigene
      Abnahme und eigene Testkörper.
- [x] **`load_operations()` brauchte über eine Sekunde — es war nicht das
      des kalten Anwendungsstarts (solidon-17): Interpreterstart 1,9 s,
      `load_operations()` 1,1–1,2 s, `build_application()` 0,9 s,
      `window.show()` 7 ms — zusammen 12,9 s beim ersten Start am Tag gegen
      2,9 s warm. Eine Sekunde davon füllt das Register mit 86 Einträgen. Ob
      das zu ändern ist, ist offen; dass es die zweitgrößte Position eines
      Starts ist, den §31 auf drei Sekunden bindet, steht hier, damit es nicht
      in einer Nachricht bleibt.

      **Gemessen am 22.08.2026, und die Antwort liegt außerhalb des
      Registers.** Je Modul gestoppt, `app.core.scene.ops` kostet **722 der
      790 ms** — die anderen achtzehn zusammen 67. Eine Ebene tiefer löst es
      sich vollständig auf: `import trimesh` **582 ms**, `numpy` 65 ms. Das
      Register selbst ist billig; `load_operations()` ist nur der Erste, der
      trimesh anfasst und deshalb die Rechnung bekommt. Die 86 Einträge kosten
      nichts Messbares — `parts.ops.register_all()` steht bei 11,8 ms.

      **Damit ist der Punkt beantwortet und die Folgefrage eine andere:** Nicht
      „wie wird das Registerfüllen schneller", sondern „muss trimesh im
      kritischen Pfad des Starts liegen".

      **Von außen nachgemessen am 23.08.2026** (kleinste von je drei Läufen,
      unter dem Schloss):

          nackter Interpreter          59 ms
          + import trimesh            739 ms   ->  trimesh allein   681 ms
          + load_operations()         888 ms   ->  davon Register   148 ms
          + PySide6                   146 ms   ->  Qt allein         88 ms
          + pyvista                   339 ms   ->  VTK allein       281 ms

      **Trimesh ist der größte Einzelposten des Starts** — mehr als Qt und VTK
      zusammen, und mehr als das Vierfache des Registers. Die Entscheidung vom
      22.08. („nicht die Stelle, an der ein Kunde etwas merkt") ist damit
      zurückgenommen: Sie stellte die halbe Sekunde gegen **12,9 s kalten**
      Start, und der ist zum größten Teil Dateisystem-Cache. Gegen die drei
      Sekunden aus §31 sind 681 ms fast ein Viertel.

      **Die Machbarkeit ist ebenfalls gemessen, und sie schließt zwei Wege aus
      und öffnet einen dritten.**

      *Trimesh teilweise laden geht nicht.* Der Import zieht `scipy.spatial`
      (168 ms) über `trimesh.grouping`, dazu `trimesh.bounds` (251 ms) und
      `trimesh.creation` (193 ms) — es gibt keinen Einstiegspunkt, der weniger
      mitbringt.

      *Trimesh in den Op-Modulen verzögern* heißt **29 Dateien** (gezählt:
      `^import trimesh` oder `^from trimesh` unter `app/core/`). Jede Funktion
      darin bräuchte den Import nach innen gezogen — machbar, aber eine
      Durchsicht und kein Handgriff.

      **Ein dritter Weg schien eine Stelle statt neunundzwanzig zu sein und
      trägt nicht:** `app/ui/app.py:234` ruft `load_operations()` vor
      `build_application()` — liefe es danach, stünde das Fenster früher. Aber
      `MainWindow.__init__` ruft `_build_menus()`, und das liest `menu_tree()`
      (3d-druck-b8, gemessen):

          load_operations()   769 ms   (zieht trimesh)
          menu_tree() danach    0 ms   (87 Einträge)

      **Die Reihenfolge ist eine echte Abhängigkeit.** Ein Fenster mit leeren
      Menüs, das sich 800 ms später füllt, ist kein Gewinn, sondern ein Tausch:
      Der Kunde kann in beiden Fällen 800 ms nichts tun — nur sieht er statt
      eines Startbildschirms, der sagt was passiert, ein Fenster, das lügt.

      **Und ein vierter Weg war ein Fehlbefund, gefangen vom Messenden
      selbst.** Die 19 Module nacheinander importiert ergab: `app.core.scene.ops`
      zieht trimesh mit 691 ms, alle anderen zusammen 52 — also *ein* Modul
      statt einer Durchsicht. Die Messung lief aber in **Reihenfolge**, und was
      `scene.ops` einmal geladen hat, findet jedes folgende Modul schon vor. Je
      Modul ein frischer Prozess sagt: **19 von 19 ziehen trimesh, 0 nicht.**

      Trimesh zu verzögern hieße damit, in neunzehn Modulen die Importe
      umzubauen — in Modulen, deren Arbeitsgrundlage es ist. Das ist kein
      Handgriff, sondern ein Umbau des Kerns.

- [x] **Ein exakter Körper mit Eckverrundungen liefert ein nicht wasserdichtes
      Netz — behoben am 23.08.2026 (`de1ce32`), und der Punkt war zu groß
      gefasst.** Es war kein Loch: Acht Dreiecke mit **Fläche null** am Pol der
      Kugelflächen, einer je Eckverrundung.

          vorher   1380 Dreiecke, 8 mit Fläche null, is_watertight False
          nachher  1372,          0,                 is_watertight True
          Euler 2, Volumen 23697,9 — beides unverändert

      **Die Oberfläche war nie kaputt**, und `is_watertight` war die falsche
      Prüfung — trimesh zählt degenerierte Kanten als offen. Der Schaden war
      trotzdem echt: Die acht wanderten bis in die exportierte STL, und
      `is_watertight` fahren viele Werkzeuge.

      **Zwei Fehlschlüsse lagen auf dem Weg, beide gemessen und verworfen:**
      `is_watertight` als Beweis für ein Loch (es ist keiner — Euler 2), und
      „die drei Knotennummern sind nicht paarweise verschieden" als Bedingung
      (OCCT vergibt am Pol *zwei* Nummern für denselben Ort; erst trimesh führt
      sie zusammen). Geprüft wird über die **Koordinaten**, behoben in
      `tessellate` und nicht am Export.

      Ursprünglich: Gemessen am 23.08.2026 (3d-druck-3a) an `to_mesh()`:

          Quader schlicht          12 Dreiecke   wasserdicht
          Quader R2 senkrecht     188 Dreiecke   wasserdicht
          Quader R2 alle Kanten  1380 Dreiecke   NICHT wasserdicht — 16 offene Kanten
          Zylinder                164 Dreiecke   wasserdicht

      **`trimesh.process(validate=True)` repariert es** — die Dreiecke sind
      also da, und die Ecken passen nicht zusammen. Der Unterschied zwischen
      der dritten Zeile und den anderen ist genau einer: Bei `'all'` entstehen
      die acht **Kugelflächen** an den Ecken, dort wo drei Verrundungen
      zusammenlaufen.

      **Eine Hypothese ist schon widerlegt:** die parallele Vernetzung
      (`isInParallel=True` in `tessellate`). Seriell ist das Netz genauso
      offen. Der Ort ist damit bekannt und die Ursache nicht.

      **Warum es zählt:** §17 verlangt wasserdichte Netze, und der Weg vom
      exakten Körper zum Druck führt durch `to_mesh()`. Ein Kunde, der einen
      exakten Quader rundum verrundet und exportiert, bekommt heute ein Netz,
      das erst eine Reparatur braucht — sie läuft, aber sie sollte nicht nötig
      sein.

- [x] **Der Start lädt nacheinander, was nebeneinander laufen könnte — gemessen
      am 23.08.2026, und es lohnt sich nicht** (3d-druck-33).

          sequenziell, wie es heute läuft   load 1,437 s + build 0,803 s
          nach dem Import, sequenziell      load 0,072 s + build 0,826 s
          nach dem Import, parallel         load 0,104 s | build 0,861 s

      **`load_operations()` selbst kostet 72 ms.** Die 1,4 Sekunden sind fast
      vollständig **Importzeit** (trimesh und was daranhängt) — und die lässt
      sich nicht parallelisieren. Die gemessene Ersparnis beträgt **37
      Millisekunden**.

      Dagegen stünde ein aufgelöster Importzyklus (Punkt unten). Kein
      Verhältnis. **Der Punkt stirbt an einer Messung, und das ist so viel
      wert wie einer, der gebaut wird — nur billiger.**

      Ursprünglich:
      `load_operations()` (769 ms, zieht trimesh) und `build_application()`
      (369 ms für Qt und VTK) laufen heute hintereinander. Sie könnten
      überlappen: Ein Arbeiter lädt die Operationen, während der Hauptthread Qt
      und VTK hochzieht, und die Menüs entstehen, wenn beide fertig sind.

      **Der Gewinn ist höchstens die kleinere der beiden Zeiten — bis zu
      369 ms**, und wie viel davon wirklich überlappt, hängt daran, wie oft die
      Importe den GIL bei I/O freigeben. Das ist eine Messung und keine
      Schätzung.

      **Der Preis ist Thread-Sicherheit beim Import**, und in einer Nacht, in
      der ein Deadlock zwischen GIL und Qt-Mutex sechs Läufe gekostet hat, ist
      das kein Nebensatz. Vorgeschlagen von 3d-druck-b8, ausdrücklich nicht für
      diese Nacht. Heute schon: `app/ui/app.py:234` ruft
      `load_operations()` vor `build_application()`, also lädt trimesh, während
      der Startbildschirm „Operationen werden geladen …" zeigt und Qt noch
      nicht hochgefahren ist. Beides parallel zu fahren wäre eine Änderung an
      der Startreihenfolge und damit eine Entscheidung — sie steht in der
      Vorlage an Robert, nicht hier. Gemessen von 3d-druck-64.
- [x] **Keine Testart deckt „zwischen zwei Modulen“ — entschieden und
      eingetragen (`452c4b5`), geprüft am 23.08.2026.** Die Testart
      **Anschluss** steht in `AGENTS.md` (Zeile 223) und Bauplan §35: *jede
      Zusage, die nur an einer Stelle eingelöst wird, wird an dieser Stelle
      geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es".*
      Bis zum 23.08. fünfmal angewandt.

      **Bemerkenswert ist, wie die Entscheidung fiel.** 3d-druck-64 hatte sie
      unter Vollmacht getroffen und auf Widerspruch zurückgenommen; 3d-druck-33
      hat stattdessen Robert direkt gefragt und ein „ja, mach rein" bekommen.
      Eine Änderung an `AGENTS.md` legt fest, *wie hier gearbeitet wird*, und
      steht damit über der Arbeit, nicht darin. Das hat eine Nacht gekostet und
      keine Substanz.

      Ursprünglich stand hier: Der Plattencache war
      vollständig gebaut (`DiskCache`, `MeshCodec`), vollständig geprüft
      (`tests/test_cache.py`) — und in der Anwendung nicht angeschlossen:
      `app/ui/session.py` baute `ResultCache()` ohne Plattenebene, `disk=`
      kam in ganz `app/` nicht vor. Jedes Öffnen rechnete den ganzen Stapel
      neu, und kein Test schlug an, weil jeder von ihnen sein Modul prüfte.
      §35 führt neunzehn Testarten; keine heißt „ist es angeschlossen".
      Beobachtung von solidon-17, und die Frage, die sie aufwirft, ist größer
      als der Cache: Wie viele fertig gebaute Sachen liegen sonst noch da,
      ohne Aufrufer?

- [x] **Acht Kundenseiten standen veraltet auf dem Server, und der Abgleich
      konnte sie nicht sehen.** Aufgefallen am 22.08.2026 beim Hochladen von
      `version.json`: Auf solidon3d.de stand noch „Demo-Fassung", wo das
      Repository seit `7d4c111` „Demo-Version" sagt — in AGB, EULA und
      Widerrufsbelehrung, also in den Texten, die im Zweifel vor Gericht
      gelten, dazu Startseite, Datenschutz, Handbuch, `site.js` und
      `style.css`.

      **Der Grund, aus dem es niemand bemerkte, ist der eigentliche Fund:**
      `upload_website.py --fehlend` verglich **Dateigrößen**, und „Fassung" und
      „Version" sind beide sieben Zeichen lang. Ein Abgleich, der Längen prüft,
      sieht eine Umbenennung nie — und eine Umbenennung ist genau das, was über
      eine ganze Website hinweg passiert. Behoben (`236009b`): Textdateien
      werden am Inhalt verglichen, und zwar **über HTTPS statt über FTP**, weil
      die ausgelieferte Adresse die Wahrheit ist, auf die es ankommt.
      Binärdateien und `.php` entscheidet weiter die Größe; PHP wird
      ausgeführt statt ausgeliefert, ein Abruf gäbe nie den Quelltext zurück.

      Alles hochgeladen und gegengeprüft: 348 Dateien oben, keine weicht ab.
      Damit ist auch die Changelog-Korrektur draußen — das Update-Fenster
      schickt den Kunden nicht mehr mit seinem achten Punkt ins Handbuch, wo
      nichts stand.

- [x] **16 Tests sagen nicht, dass ihre Grundmenge nicht leer ist — abgearbeitet
      am 23.08.2026 (`1fd00af`, 3d-druck-33).** 29 Kandidaten, **14 echte
      Lücken**, 15 keine. Der Unterschied ist die Regel, und sie ist der
      eigentliche Ertrag des Punktes:

      > Eine Grundmenge braucht die Zusicherung, wenn sie **erhoben** wird —
      > aus dem Dateisystem, aus einem Ladevorgang, aus einer gebauten
      > Oberfläche. Steht sie als Konstante im Modul (`REQUIRED_LINKS`,
      > `FIELDS`, ein Dict-Literal mit drei Einträgen), kann sie nicht
      > unbemerkt leer werden, und die Zeile wäre Zierat.

      **Der Satz, der hier vorher stand, war die erste von zwei Fassungen und
      falsch.** „Das Muster für die Behebung ist eine Zeile“ — eingebaut
      hat sie **elf Tests rot gemacht**: Eine leere `__init__.py` hat legitim
      keine Bezeichner, die Zusicherung gehört eine Ebene höher. Niemand hatte
      den Satz ausprobiert, bevor er im Register stand. Überall eine Zeile
      wäre 15-mal Rauschen gewesen, das beim nächsten Lesen niemand mehr von
      den 14 echten unterscheidet.

      **Zwei der 14 sind der Fund des Punktes, und beide sind unsichtbar
      gescheitert statt rot:**

      `source_files()` in `test_language_rules.py` trägt **vier
      parametrisierte Tests**. Ist die Liste leer, werden sie nicht rot —
      pytest sammelt null Tests, meldet `no tests ran` und gibt **Exit 5**.
      Eine Zusicherung *in* den Tests hätte nie gegriffen, weil sie nie
      gelaufen wäre; sie steht jetzt in der Funktion, die die Parameterliste
      liefert. Es ist derselbe Exit 5, über den `suite-getrennt.sh` schon
      einmal gestolpert ist — dort als lauter Fehllauf, hier als stiller
      Erfolg.

      `test_interface_limits.py`: Jede Grenze dort ist eine **Obergrenze**.
      Ein leeres Register unterschreitet jede davon — höchstens neun
      Menüs, zwölf Zeilen, acht Umschalter, alles grün, nichts geprüft. Ohne
      `load_operations()` hat das Register null statt 87 Operationen, und das
      ist der Fall, der hier real vorkommt.

      Sechs von sechs mutierbaren Fällen sind gegengeprobt: Grundmenge
      geleert, Test rot, zurückgestellt. Die übrigen acht sind
      `assert len(x) > n` direkt über der Erhebung, dort wäre die Probe
      Tautologie.

      **Und der Zähler, der die 29 fand, hat selbst zwei falsch einsortiert**
      — von Hand gefunden: `test_theme_and_palette.py` war längst
      gesichert, `source_files()` galt ihm als Konstante, obwohl es ein Glob
      ist. *Auch ein Zähler misst, was sein Muster kennt.*

      Ursprünglich: Durchgesehen am 23.08.2026 von 3d-druck-3a, und der Punkt
      hat damit eine Methode statt einer Anekdote.

      **Die ursprüngliche Frage traf daneben.** Sie lautete *„misst der Test
      gegen einen Wert von außen oder nur gegen die eigene Wiederholbarkeit?"*
      — die ersten Treffer waren `first.volume == approx(second.volume)`, also
      Determinismus-Prüfungen, und die sind eine **eigene Testart** aus
      `AGENTS.md`. Jede einzelne legitim.

      **Die Frage, die trifft, ist eine andere:**

      > Was wäre eine Implementierung, die diesen Test besteht und die Sache
      > trotzdem nicht tut?

      **Damit wird es maschinell findbar:**

          Tests, die ausschließlich Verbote prüfen      108
          davon über eine gefilterte Menge               16  <- die scharfe Liste
          davon nachgeprüft                               5  <- alle fünf gedeckt

      **Die Zahl stand zuerst bei 26 und ist nachgeprüft 16.** Der Zähler hatte
      `for x in <name>` gelesen und dabei Schleifenvariablen für Grundmengen
      gehalten — `range`, `ast`, `re` zählten mit. Nachgeprüft von 3d-druck-3a
      selbst, ausgelöst durch eine verwandte Falle bei 3d-druck-b8, deren
      Artikelzähler an einem Teilstring hängenblieb (`le plaque` steckt in
      `seule plaque`). *Wer mit derselben Sorte Muster gezählt hat, zählt seine
      eigenen Zahlen nach.*

      **Und der Befund ist kleiner, als er zuerst aussah:** Fünf der sechzehn
      sind einzeln geprüft, **alle fünf gedeckt** — `generated_body()` liefert 4
      Merkmale, `cube()` 6, `plate()` 10, `test_every_file_the_page_refers_to_exists`
      prüft 1517 Verweise über 30 Seiten, und `test_every_operation_has_exactly
      _one_menu_entry` bekommt sein Register aus einer Fixture.

      **Offen ist damit kein Schaden, sondern eine fehlende Zusicherung.** Kein
      Test ist heute falsch grün; keiner *sagt*, warum er es nicht ist. Fällt
      die Fixture weg, prüft `test_every_operation…` 61 Operationen statt 77 und
      bleibt still.

      Ein `assert not [x for x in menge if …]` ist grün, wenn `menge` leer ist.
      Die `test_every_…`-Namen darin sind der Typ, bei dem es wehtut:
      *„jede Operation hat genau einen Menüeintrag"* ist grün, wenn das
      Register leer ist. Nachgeprüft ist er gedeckt — `load_operations()` steht
      in einer Fixture —, **aber er sagt es nicht selbst**: Fällt die Fixture
      weg, prüft er 61 Operationen statt 77 und bleibt grün. (Genau diese
      Differenz steht als eigene Erinnerung: ohne `load_operations()` fehlen
      die sechzehn aus der Bausteinbibliothek.)

      **„Das Muster für die Behebung ist eine Zeile" — und auch das stimmt
      nicht.** Hier stand, ein Verbotstest brauche daneben nur
      `assert menge, "sonst prüft dieser Test nichts"`. Am 23.08.2026 einmal
      eingebaut, in `test_language_rules.py`: **elf Tests wurden rot.** Eine
      leere `__init__.py` hat legitim keine Bezeichner, und die Zusicherung
      gehört dort eine Ebene höher — auf die **Parameterliste** statt auf die
      Menge im Test. Zurückgenommen, Suite wieder grün.

      **Damit sind die Kandidaten einzeln durchzugehen und nicht zu ersetzen.**
      Die Zahl ist dabei auch gewachsen: Ein zweiter Zähler findet **35**
      Kandidaten, davon 29 in einem Gebiet — gegen die 16 von vorhin. Welche
      der beiden Zählungen die richtige Frage stellt, ist offen; **beide sind
      Verdachtslisten und keine Fehlerlisten.**

      **Drei sind behoben, alle gemessen statt vermutet:**

          open_edges > 0            ->  == 5        „>0" ließ 12 als 1 durch
          all(d >= 0.5 for d …)     ->  not holes   all() über leer ist wahr;
                                                    der Test hatte nie etwas geprüft
          not [… kind == "hole"]    ->  sagt jetzt, was es *ist*

      Der zweite ist der lehrreichste: `detect_holes` liefert auf dem
      organischen Netz **null** Bohrungen, und `all()` über eine leere Liste
      ist `True`. Grün, ohne je etwas geprüft zu haben — und er hätte einen
      Kratzer durchgelassen, der als Ø2 gemeldet wird, weil die Schwelle nur
      *sehr kleine* Falschmeldungen fängt.

      **Vier weitere sind geprüft und als gedeckt belegt** statt angefasst:
      Gemessen, dass die Quellen wirklich liefern (`generated_body()` 4
      Merkmale, `cube()` 6, `plate()` 10). Ein Verbotstest über eine Quelle,
      die nachweislich liefert, ist in Ordnung — die Lücke ist nur, dass die
      Deckung nirgends im Test steht.

      **Offen sind die 26**, und sie verteilen sich über alle Gebiete.

- [ ] **Ein Test, der nur seine eigene Konsistenz misst, sieht keinen
      systematischen Versatz.** Zweimal an einem Tag gefunden, beide Male
      hätte die naheliegende Prüfung geschwiegen:

      * **Die Krümmungskarte** rechnete durchweg **genau zwei Drittel** des
        wahren Radius (3,33 statt 5), weil sie ab dem Dreiecksschwerpunkt maß
        statt ab der Mitte der ebenen Fläche. Der Fehler war bei **jeder**
        Netzfeinheit gleich groß — ein Test, der zwei Vernetzungen
        gegeneinander hält, wäre grün geblieben. Gefunden wurde er, weil gegen
        den **Sollwert** geprüft wurde (Zylinder r=5) und nicht gegen die
        eigene Wiederholbarkeit.
      * **`ring_diameter`** machte die Größenkomponente des Merkmalsvektors zu
        null, weil `feature_vector` den Schlüssel `diameter` liest. Zwei Tori
        verschiedener Größe kosteten gegeneinander 0,0 — für die Zuordnung
        dasselbe Merkmal. 41 Merkmalstests, die Registerkonsistenz und die
        Zuordnungstests blieben grün, weil sie Bohrungen prüfen, und die
        heißen richtig.

      **Was daraus folgt, ist keine neue Testart, sondern eine Frage an jede
      vorhandene:** Prüft sie gegen einen Wert, der von außen kommt — ein
      Sollmaß, eine andere Rechnung, eine analytische Formel —, oder nur
      dagegen, dass zweimal dasselbe herauskommt? Determinismus ist billig zu
      prüfen und fängt genau die Fehler nicht, die immer gleich falsch sind.
      Verwandt mit der Testart „Anschluss" (§35): Auch dort ist jeder Test für
      sich grün.

      **Der Versuch, die Frage automatisch zu stellen, ist am 23.08.2026
      gescheitert — und zwar aus einem Grund, der zum Punkt selbst gehört.**
      Ein Zähler über die Asserts der Geometrietests meldete 398 „mit Sollwert"
      gegen 76 „nur Selbstvergleich". Beide Zahlen sind wertlos:

      * Der Dateifilter zog `test_analysis_ui.py` herein — Oberflächentests,
        weil „analysis" im Namen steht. Wieder eine Mustersuche, die misst, was
        ihr Muster kennt.
      * **Und der eigentliche Fall ist maschinell gar nicht sichtbar.**
        `assert volume == pytest.approx(31276.892)` sieht wie ein Sollwert aus.
        Ob die Zahl analytisch hergeleitet oder aus einem früheren Lauf
        abgeschrieben wurde, steht nirgends im Code — im zweiten Fall ist sie
        Selbstkonsistenz in Verkleidung und würde einen systematischen Versatz
        genauso mittragen wie ein Determinismustest.

      Damit bleibt es bei der Handarbeit, und der Punkt ist danach zu
      schneiden: **je Kennzahl fragen, woher ihr Sollwert stammt**, angefangen
      bei denen, die eine Geometrie beschreiben (Krümmung, Durchmesser,
      Volumen, Achsen). Wo die Herleitung fehlt, gehört sie als Kommentar
      dazu — das ist die einzige Form, in der die Antwort haltbar ist.

- [x] **Ein mitgeliefertes Beispiel fragte beim Öffnen viermal nach Kegeln.**
      Gemessen am 22.08.2026 an `aushoehlen-und-teilen.p3d` mit einem
      protokollierenden ``ask``: vier modale Fenster, „Welches Merkmal
      entspricht cone_1?" gegen `cone_2`, und die vierte Frage wiederholte die
      erste. Ohne ``ask`` warf `_refuse_to_guess`, und
      `test_an_example_opens_and_computes[aushoehlen-und-teilen]` war rot.

      **Warum das schwerer wog als ein roter Test.** Ein Kunde öffnet ein
      **mitgeliefertes Beispiel** — den freundlichsten Weg, den die Anwendung
      hat (§2.2) — und bekommt vier Fenster, die ihn nach `cone_1` gegen
      `cone_2` fragen. Er weiß nicht, was ein `cone_1` ist, es gibt keinen
      richtigen Antwortknopf, und die vierte Frage wiederholt die erste.
      Anhalten und Fragen ist Regel 21 und richtig; **diese** Frage war es
      nicht.

      **Behoben am selben Tag — und die Ursache war eine andere als die erste
      Diagnose.** 3d-druck-64 hatte auf zwei gespiegelte Senkungen getippt, die
      für `feature_vector` gleich weit entfernt liegen. Das trifft zu und war
      trotzdem nicht der Grund. 3d-druck-3a hat gemessen statt angenommen:
      `CURVATURE_JUMP` testweise so gesetzt, dass nie nachgetrennt wird — also
      den Zustand vor ihrer eigenen Änderung —, und dasselbe Beispiel gefahren.

          ohne Krümmungstrennung -> complete: True    obj_2: cone 2
          mit  Krümmungstrennung -> complete: False   obj_2: cone 3

      **Die neue Trennung hatte einen Kegel in zwei zerlegt.** Erst dadurch
      wurden `cone_1` und `cone_2` zu Rivalen. Der Grund ist eine Eigenschaft
      des Kegels, die Torus und Zylinder nicht haben: **Er hat keine feste
      Krümmung.** Sein Querradius wächst zur Grundfläche hin stetig, und über
      eine lange Senkung summiert sich das zu einem Sprung, der wie eine
      Flächengrenze aussieht.

      Behoben mit demselben Prinzip, das an diesem Tag schon zweimal getragen
      hat: **additiv am Ende.** Nachgetrennt wird nur noch, wenn auf den Fleck
      keine einzige Form gepasst hat — wo etwas erkannt wurde, bleibt es. Damit
      kann der Fall **strukturell** nicht wiederkommen, nicht bloß in diesem
      Beispiel. Über den ganzen Korpus: null Änderung an achtzehn Körpern.

      *Zwei Lehren, die bleiben:* Die erste Diagnose war plausibel, naheliegend
      und falsch — widerlegt hat sie eine Messung, die den **eigenen** letzten
      Eingriff versuchsweise zurücknimmt. Und der Fall zeigt die Grenze von
      §15.7: Beim zweiten Öffnen stünde die Antwort im Stapel und es käme keine
      Frage mehr. Beim ersten schon — und das erste ist das, was ein Kunde
      erlebt.

- [x] **Eine verrundete Quaderkante wurde als „Zapfen Ø 28,9" gemeldet.**
      Gemessen am 22.08.2026 an einem verifizierten Testkörper — Quader
      40 × 30 × 20, eine Kante mit R 3 ausgerundet, Volumen exakt 23942 gegen
      Sollwert 23942:

          Erkennung: {'face': 4, 'pin': 1}
            pin_1  Ø 28,92   (r = 14,46)
          Krümmungskarte: 3,0 mm      <- die richtige Antwort steht daneben

      **Die erste Diagnose war `fit_cylinder`, und sie war falsch.** Sie lautete:
      Bei einem 90-Grad-Ausschnitt liegen die Normalen auf einem Bogen statt auf
      einem Kreis, es gibt keinen klaren Nullraum, die Achse wandert. Plausibel,
      und beim Nachbauen widerlegt.

      **Die Ursache liegt eine Stufe früher, in der Facettenklassifikation.**
      Zwei **ebene** Facetten von 1110 und 510 mm² — auf einem Körper mit
      1200 mm² größter Fläche — galten als „gekrümmt", weil sie die Rundung
      berühren. Sie hängten sich dem Verrundungsfleck an, und die Kåsa-Einpassung
      gewichtet quadratisch: vier Punkte in bis zu 25 mm Abstand ziehen einen
      Kreis von r=3 auf r=14,46. **Die Einpassung war nie das Problem — sie bekam
      den falschen Fleck.** Das ist eine andere Sache als ein kaputter Löser, und
      wer es verwechselt, sucht an der falschen Stelle.

      **Das ist ein Fehlbefund, kein fehlender Befund — und darin liegt der
      Unterschied zur Kehlensäule.** Dort fand die Erkennung *nichts*: schlecht,
      aber ehrlich. Hier findet sie etwas Falsches, `applies_to` bietet daran
      Zapfen-Operationen an, und §14 sagt, ein Zapfen sei das, was man mit einer
      Bohrung paart. Mit diesem paart niemand etwas. Für einen Kunden ist das
      die schlechtere Sorte Fehler: Ein Werkzeug, das schweigt, lässt ihn selbst
      nachsehen; eines, das etwas Falsches behauptet, führt ihn weg.

      **Zwei Schranken greifen nicht.** `_fits_in_the_body` lässt Ø 28,9 durch —
      das passt quer in einen 40er Körper, und die Schranke war gegen Ø 631
      gebaut, nicht gegen das Fünffache. Und die Regel „nachtrennen nur, wo
      keine Form gepasst hat" (vom selben Tag) greift ebenfalls nicht: Hier hat
      eine gepasst, nur die falsche. Das ist die Kehrseite jener Regel und war
      der Preis dafür, dass die Senkung im Beispielprojekt nicht zerfällt.

      **Die Reichweite ist vermutlich größer als der Anlass:** Jede
      angeschnittene Bohrung, jede halbe Nut, jeder Zylinder am Rand eines
      Teils geht denselben Weg. Der Umbau ist bekannt und zweistufig wie beim
      Torus — Achse über das lineare Rotationsflächen-System, Radius über
      `_fit_circle`, beides liegt fertig in `features.py`. **Er gehört an den
      Anfang einer Sitzung mit vollem Tor dahinter**, denn `fit_cylinder` ist
      die Einpassung, an der jede Bohrung und jeder Zapfen hängt. Gefunden von
      3d-druck-3a beim Verrundungsradius.

      **Behoben am 22.08.2026 (`e3b01b7`):**

          verrundete Quaderkante:   Ø 28,924  ->  Ø 5,997
          Flächen daneben:          4         ->  6
          Korpus, 13 Zylinder:      0 geändert (vier Stellen, gesicherte Grundlinie)
          neuer Körper:             block_with_rounded_edge.stl (23942 mm³)

      Behoben eine Stufe über dem Löser, in `_large_facet_faces`, über eine
      zweite Schwelle am Anteil der **Gesamtoberfläche** (21 % und 10 % für die
      zwei ebenen Facetten gegen 0,09 % für einen Mantelstreifen).

      **Ein Irrweg gehört dazu, weil er die Falle beschreibt:** Die erste
      Schwelle maß am Anteil der **größten Facette**. Ein Torus besteht nur aus
      Mantelstreifen — seine größte Facette ist selbst einer —, also lag jede
      bei fast hundert Prozent, und `torus_ring.stl` zerfiel in 288 ebene
      Flächen. Der Kommentar in der Funktion warnt wörtlich davor.

      **Und ein zweiter Fund, den erst das volle Tor zeigte:** Die Nachtrennung
      rechnete die Krümmung über **alle** Nachbarpaare des Körpers, und zwar je
      Fleck ohne Form. An `dense_1m.stl` (1,3 Mio. Dreiecke) sind das 11,3 s und
      **395 MB Spitze** — mal acht parallele Prozesse über drei Gigabyte. Das
      waren die elf Fehlschläge, die zuvor der Fremdlast zugeschrieben worden
      waren.

- [x] **Der Rückstand sieht einen falschen Zylinder nicht — behoben am
      22.08.2026 (`9257c0d`, 3d-druck-3a).** `CylinderFit.spread` misst
      **absolut in Facettenbreiten** statt relativ; ein Viertelbogen, der als
      Zylinder mit r = 89,79 statt 3 eingepasst wird, fällt damit durch. Der
      alte Rückstand belohnte genau das, was er fangen sollte — je größer der
      falsche Radius, desto flacher der Bogen und desto kleiner der relative
      Fehler.

      Ursprünglich: Beim Fall darüber
      lag der Rückstand der Einpassung bei **0,0313** — weit unter
      `CYLINDER_TOLERANCE` (0,08) — während der Radius um das **Fünffache**
      danebenlag. Ein Wächter, der eine Einpassung nur an ihrem Rückstand misst,
      hält also eine Form für gut, die um 400 Prozent falsch ist.

      **Beim Torus funktioniert derselbe Wächter**, und das ist der interessante
      Teil: Dort lehnt der Rückstand einen Zweiundzwanzig-Grad-Span ab
      (`good=False`, 0,078 über der Schwelle). Warum er beim Zylinder blind ist
      und beim Torus nicht, gehört **gemessen und nicht angenommen** — die
      naheliegende Vermutung ist, dass ein zu großer Zylinder durch einen
      schmalen Bogen fast genauso gut hindurchgeht wie der richtige, während ein
      Torus zwei Radien hat und schon einer davon die Abweichung sichtbar macht.

- [x] **Die Krümmungskarte misst das Netz und nicht den Körper — behoben am
      23.08.2026 (`eb1a541`, 3d-druck-3a).** Sie zeigt jetzt **Radien in
      Millimetern** statt des schärfsten Winkels zu einem Nachbarn. Der
      Unterschied ist an einer Zahl abzulesen: Derselbe Zylinder ergibt bei 32
      und bei 128 Segmenten 4,97 und 5,00 mm — vorher hing die Aussage an der
      Vernetzungsdichte, und genau das ist bei einer Verrundung der Fehler: Je
      feiner sie vernetzt ist, desto kleiner der Winkel je Facette, obwohl der
      Radius derselbe bleibt.

      Ursprünglich:
      `curvature_map` (`app/core/perceive/maps.py`) ist gebaut, registriert und
      hat Titel, Einheit und Legende — sie misst aber `face_adjacency_angles`
      in **Grad**. Ihr eigener Docstring nennt die Folge: „Kanten stechen
      hervor, **Verrundungen bleiben glatt**." Damit ist eine Verrundung per
      Konstruktion unsichtbar, denn ein kleiner Winkel je Facette ist ihr
      Zweck — und schlimmer: Je feiner sie vernetzt ist, desto glatter sieht
      sie aus, obwohl der Radius derselbe bleibt. **Eine Karte, deren Aussage
      von der Vernetzungsdichte abhängt, misst das Netz.**

      Der Fix ist eine Division: Winkel geteilt durch Kantenlänge ist die
      Krümmung, ihr Kehrwert der Radius. Gemessen an einem Kehlkörper trennt
      das sauber — 0,33 → 3,03 mm (Kehle, echt 3,0), 0,16 → 6,25 mm (Säule,
      echt 6,0), 0,11 → 9,09 mm (Ringradius, echt 9,0), 0,00 für die ebenen
      Anteile; drei Gruppen zu je 192 Kanten und eine zu 1546. Bauart,
      Registrierung und Anbindung der Karte bleiben.

      **Entschieden (22.08.2026): Krümmung als Wert, Radius in Legende und
      Beschriftung.** Der Radius ist das, wonach gefragt wird, taugt aber nicht
      als Skala — eine Ebene hat Radius unendlich. Die Krümmung hat die Ebene
      bei 0 und die scharfe Kante am oberen Ende; dass der Nutzer trotzdem
      Millimeter liest, ist die Trennung zwischen dem, was gerechnet wird, und
      dem, was dasteht (§18.4: „Immer mit Legende und Zahlenbereich").
      Gefunden von 3d-druck-3a.

- [x] **An einer Säule mit verrundetem Fuß erkennt die Wahrnehmung keinen
      Zylinder** — gebaut (`6efda06`), nachgemessen am 23.08.2026:
      `{'pin': 1, 'torus': 1, 'face': 7}`, Zapfen Ø12,0 wird erkannt. Die
      Trennung nach **Krümmung** statt nach Knick steht.

      Ursprünglich: Gemessen am 22.08.2026 an einem echten Kehlkörper (Säule Ø12
      auf Platte, Kehle R=3, wasserdicht, 2704 Dreiecke): sieben Flächen und
      **kein einziger Zylinder**. Säule und Kehle sind ein einziger Fleck mit
      2305 Dreiecken.

      **Der Grund ist keine Schwäche der Segmentierung, sondern die Sache
      selbst.** `_connected_patches` trennt über `CURVATURE_LIMIT`, also an
      Knicken — und eine Verrundung schließt **tangential** an, das ist ihr
      Zweck. Die gesenkte Bohrung war der leichte Fall (45-Grad-Knick); dies ist
      der harte. Was fehlt, ist eine Trennung **nach Krümmung** statt nach
      Knick, und die ist der Schlüssel für alles tangential Angeschlossene —
      nicht nur für Verrundungen.

      Die Folgen gehen über die Anzeige hinaus: Der Agent kann auf die
      Mantelfläche nicht zeigen (Leitprinzip 5), keine Bohrungs- oder
      Passungs-Operation findet sie, der Steckbrief nennt sie nicht. Eine Säule
      mit verrundetem Fuß ist ein Alltagsteil. Gefunden von 3d-druck-3a bei der
      Vorarbeit zum Verrundungsradius.

- [x] **Der Testkorpus hat keinen verrundeten Körper — behoben, geprüft am
      23.08.2026.** Er hat jetzt drei: `block_with_rounded_edge.stl` (Quader
      mit ausgerundeter Kante, von `test_features.py` gelesen),
      `post_with_fillet.stl` (Säule mit Kehle) und
      `plate_chamfer_and_taper.stl` (Fase und Verjüngung). Angelegt von
      3d-druck-3a beim Verrundungsradius.

      **Ein Rest bleibt und ist eine Zeile wert:** `post_with_fillet.stl` liegt
      im Korpus, aber kein Test liest ihn. Eine Korpusdatei ohne Leser ist
      derselbe Nichtanschluss wie eine Funktion ohne Aufrufer — sie sieht wie
      Abdeckung aus und ist keine. Gehört zu 3d-druck-3a, gemeldet am 23.08.

      Ursprünglich stand hier: Deshalb fiel der Punkt darüber bis zum
      22.08.2026 niemandem auf — nicht weil die Erkennung
      besser war, sondern weil nie jemand mit einer Kehle danach gefragt hat.
      §34 nennt den Korpus das Regressionsnetz der Wahrnehmung; ein Netz, das
      genau die Alltagsformen ausspart, meldet Erfolg über dem, was es nicht
      enthält.

- [x] **In `parts/` ist der Nichtanschluss ein Rückfall — angeschlossen,
      geprüft am 23.08.2026.** `travelling_parts()` hat jetzt einen Aufrufer
      (`parts/check.py:100`, Befund `parts.travelling`) und einen Test
      (`test_parts_catalog.py:435`). Die Testart „Anschluss" steht seit dem
      22.08. in `AGENTS.md` und Bauplan §35 — der Rückfall hat also nicht nur
      eine Behebung bekommen, sondern die Prüfung, die ihn beim nächsten Mal
      fängt.

      Der Befund selbst bleibt lesenswert, weil er das Argument für diese
      Testart trägt: `tests/test_parts_catalog.py` schließt mit einem Test, dessen Docstring
      lautet: „§24.5 stand nur auf dem Papier: `parts/user.py::load()` hatte
      keinen Aufrufer im Produkt — eigene Bausteine wurden nie geladen." Der
      Fehler wurde also **schon einmal gefunden und behoben**. In derselben
      Datei liegen jetzt `travelling_parts()` und `check.stamp()` mit demselben
      Fehler; bei `stamp()` ist er am 22.08.2026 geschlossen worden
      (`9b12166`), `travelling_parts()` steht weiter ohne Aufrufer und ohne
      Test da — und behauptet in ihrem Docstring im **Indikativ**, sie werde
      beim Speichern und beim Öffnen benutzt.

      **Das ist das Argument für die Testart „Anschluss" (§35), und es ist
      stärker als jeder Einzelfall:** Nicht „so etwas passiert", sondern „so
      etwas passiert **wieder**, an derselben Stelle, nachdem es dort schon
      einmal auffiel". Ein Mensch, der zweimal hinsieht, hat es nicht gefangen.
      Gezählt sind es damit an einem Tag fünf: Plattencache, `detect_holes()`
      gegen `detect()`, `travelling_parts()`, `check.stamp()` und der
      Rückfall selbst.

- [x] **Der Ring-Umbau hob die Absturzquote von 1/10 auf 6/10 — gemessen von
      dem, der ihn gebaut hat.** 3d-druck-b8 hat ihren eigenen Umbau gegen einen
      Arbeitsbaum auf dem Stand davor gefahren und den Preis beziffert, statt
      ihn zu vermuten:

          test_pose_session      vor Ringen 1/10   mit Ringen 6/10   mit Schutz 1/10
          test_sculpt_session    vor Ringen 1/10   mit Ringen 2/10   mit Schutz 0/10
          Fehlläufe im Tor            —                 6/28              3/28

      Der Fehler ist `0xC0000374` — **Heap Corruption in `wait_for_idle`, mitten
      in `processEvents`.** Die Mechanik ist eine andere als zuerst vermutet:
      Nicht ein fremder Thread zerstört, sondern **der Speicherbereiniger räumt
      im Hauptthread ab, während Qt denselben Widgets Ereignisse zustellt.** Bis
      zum 22.08.2026 konnte das nicht passieren, weil nie ein Fenster
      freigegeben wurde.

      **Behoben mit `undisturbed()`, ohne den Umbau zurückzunehmen** — der Ring
      bleibt weg, die Freigabe bleibt, nur räumt sie nicht mehr in eine laufende
      Ereigniszustellung hinein.

      *Was diesen Punkt lehrreich macht, ist nicht der Fehler, sondern die
      Messung:* Der Umbau war fertig, gemessen (20 von 20 Fenstern freigegeben)
      und committet. Ihn danach **gegen sich selbst** zu prüfen — alter Stand im
      eigenen Arbeitsbaum, zehn Läufe je Seite — hätte niemand verlangt. Ohne
      diese Messung wäre aus „7 MB je Fenster gespart" ein Absturz in sechs von
      zehn Läufen geworden, und niemand hätte die beiden Dinge verbunden.

- [ ] **Parallelität und Schloss sind keine Alternativen — sie bedingen
      einander.** Gemessen am 22.08.2026 von 3d-druck-b8: dieselbe Sammelgruppe
      zweimal mit `-n 8` gefahren, einmal **11 failed**, einmal **0 failed**.
      Der Unterschied war kein Code, sondern ein fremder Torlauf, der mitlief.

      **Die erste Zuordnung war Fremdlast, und sie war falsch.** Sie lautete:
      Acht Prozesse lasten die Maschine so aus, dass der fremde Lauf kippt.
      3d-druck-b8 hat sie selbst zurückgenommen, nachdem 3d-druck-3a die
      wirkliche Ursache gemessen hatte: **Die Nachtrennung rechnete die
      Krümmung über alle Nachbarpaare des Körpers, und zwar je Fleck, der keine
      Form ergeben hatte.** An `dense_1m.stl` (1,3 Mio. Dreiecke) sind das
      **11,3 s und 395 MB Spitze** — mal acht parallele Prozesse über drei
      Gigabyte. Die elf Fehlschläge kamen aus dem Speicher, nicht aus der
      Rechenlast.

      **Die Folgerung bleibt trotzdem stehen, nur mit besserem Grund:** Wer die
      Parallelität ausbaut, braucht das Schloss **strenger** — nicht weil
      Prozesse sich die Rechenzeit nehmen, sondern weil jeder von ihnen
      denselben Speicher achtmal belegt. Ein Test, der allein 395 MB braucht,
      ist parallel etwas ganz anderes als seriell, und das sieht man ihm
      seriell nicht an.

      Die ältere Beobachtung dazu bleibt gültig und unabhängig: Fremdlast macht
      funktionale Qt-Tests rot, nicht langsam (gemessen, acht Minuten
      Stillstand und ein Exit 139).

      Dieselbe Sache hatte am selben Tag schon einmal acht Minuten Stillstand
      und einen Exit 139 gekostet, und sie stand danach als Regel in
      `.claude/rules/tests.md`: Fremdlast macht funktionale Qt-Tests rot, nicht
      langsam. Ein geschrumpftes Schloss wäre dieser Fehler als
      Dauereinrichtung.

      **Die Zahlen zur Toränderung, gemessen statt geschätzt.** Maschine
      i9-13900K, 24 Kerne; Auslastung während eines Torlaufs mit drei wartenden
      Sitzungen **16 %**. Sammelgruppe seriell 175 s, mit `-n 8` 66 s (Faktor
      2,6), mit `-n auto` (32) scheitert der Verteiler.

      **Und dann der Lauf auf leerer Maschine, der die eigentliche Frage
      beantwortet:**

          Tor insgesamt              5 min 09 s
            Suite (mit -n 8)           259 s
            Leistungstests              49 s
            ruff, format, mypy           1 s

      **Fünf Minuten gegen dreißig beobachtete.** Die Lücke schließt sich
      vollständig — und sie kam **nicht** aus der Testzeit, sondern aus
      Wartezeit, Fremdlast und Hängern. Gemessen wurde die Gesamtdauer von
      außen (Startzeit bis Endzeit) statt als Summe der Protokollzeilen; genau
      dort hatte die Lücke bisher gesteckt, weil eine Summe von Zeilen jede
      Pause dazwischen verschweigt.

      Daraus folgt die Reihenfolge, und sie ist damit belegt statt vermutet:
      **erst der Deadlock, dann die Parallelität.** Was 109 Sekunden spart, ist
      zweitrangig neben dem, was 10 bis 27 Minuten kostet.

- [ ] **Ein gescheiterter Merge ist ein Eingriff, kein Nichts.** Gefunden am
      23.08.2026 im geteilten Arbeitsbaum: Um 01:18 trug der Baum eine
      **ältere** Fassung zweier Dateien, als committet war — elf Zeilen in
      `tools/make_examples.py` fehlten, und `app/examples/*.p3d` trugen den
      ZIP-Stempel von vor ihrer Reparatur. Kein Commit hatte das getan.

      **Der Reflog nannte den Grund** (3d-druck-b8, Selbstanzeige):

          abce5f3  HEAD@{01:18:08}  merge b8/merge-nach-main: updating HEAD
          error: Your local changes to the following files would be overwritten
          Index was not unstashed.
          Merge with strategy ort failed.

      **„Index was not unstashed" ist die Zeile, die zählt.** Git legt vor
      einem Merge einen Autostash an, wenn der Baum schmutzig ist, bewegt HEAD,
      schreibt Dateien — und spielt den Stash bei einem Abbruch **nicht**
      zurück. Ein „Merge failed" heißt also nicht „nichts passiert": Der
      Versuch hat HEAD bewegt und Arbeitsbaumdateien auf den Stand des
      Merge-Ziels gesetzt.

      **Die Regel daraus:** *Wer einen Merge abbricht, prüft danach
      `git status` **und** `git stash list`.* Der Autostash überlebt den
      Abbruch nicht zuverlässig, und im geteilten Baum trifft er fremde Arbeit.

      **Und es ist das dritte Mal an einem Tag, dass eine wahre Aussage nicht
      die ganze war** — „der Zeitstempel ist die Ursache", „es ist Fremdlast",
      „der Merge ist gescheitert". Jede stimmte, keine reichte.

- [ ] **Der Haupt-Index altert, und `git status` lügt für alle anderen mit.**
      Zum zweiten Mal in einer Nacht: Weil alle vier Sitzungen mit
      `GIT_INDEX_FILE` committen, zieht niemand den gemeinsamen Index nach. Am
      23.08. stand er bei **106 Hinzufügungen gegen 1424 Löschungen** gegenüber
      `HEAD` — ein nacktes `git commit -a` hätte 1424 Zeilen gelöscht.

      **Der Schaden ist nicht der Index selbst, sondern was er anderen
      erzählt:** `git status` zeigt fremde Dateien als `MM` und lässt eine
      Sitzung glauben, jemand habe dort ungestagte Arbeit liegen. In dieser
      Nacht hat das zweimal zu einer Rückfrage geführt, die sich in Luft
      auflöste — und einmal fast dazu, dass eine Datei nicht angefasst wurde,
      die frei war.

      Aufgeräumt wird mit `git reset` (ohne Pfade, ohne `--hard`): Der Index
      geht auf `HEAD`, der Arbeitsbaum bleibt unberührt. **Vorher `.git/index`
      kopieren** — geprüft, dass nichts nur dort liegt (`--name-status | grep
      ^A`), dann zurücksetzen. Zu klären bleibt, ob das Verfahren mit privatem
      Index den Nachzug selbst übernehmen kann.

- [ ] **Das Prüfschloss serialisiert die Rechenzeit, nicht den Arbeitsbaum.**
      `tools/gate_lock.py` schützt vor Fremd*last* — gegen Fremd*stände* hilft
      es nicht: Jeder Lauf liest die ungestageten Dateien aller Sitzungen, egal
      wie halb fertig sie gerade sind. Am 22.08.2026 meldete ein Tor-Lauf einen
      roten Test mit einem Bild, das keinen Sinn ergab: Der Aufruf übergab
      `create_box`, der Draft im Fehlertext hieß `thicken`. Es war dieselbe
      Datei in zwei Fassungen — eine Sitzung schrieb sie gerade um, während die
      andere sie prüfte.

      **Gefährlich ist nicht der falsche Fehler, sondern der falsche Erfolg.**
      Ein fremder Zwischenstand kann einen Lauf auch grün machen, und dann hält
      eine Sitzung ihre eigene Arbeit für abgesichert, die es nicht ist.
      Naheliegende Antwort sind eigene Arbeitsbäume unter `.claude/worktrees/`
      mit dem bekannten Preis — dort gibt es kein `.venv`, der Interpreter muss
      mit vollem Pfad aus dem Hauptbaum gerufen werden (gemessen am 22.08., die
      Suite läuft so).

      **In der Nacht zum 23.08.2026 ist der Punkt entscheidungsreif geworden:
      drei Fälle in einer Nacht, jeder mit einer anderen Gestalt.**

      1. **Im Prüfling.** 27 rote Tests über zwölf Dateien, alle mit derselben
         Zeile — `ImportError: cannot import name 'pair_radii'`. `maps.py` trug
         den Import seit 20:36, `features.py` bekam die Funktion um 00:02:47.
         Ein Torlauf fiel genau in die Lücke. (Ursache war ein Aufräum-Skript,
         das beim Entfernen zweier verwaister Konstanten fünf Funktionen
         mitgelöscht hatte.)
      2. **Im Prüfwerkzeug.** Ein Lauf starb an einem Syntaxfehler in
         `suite-getrennt.sh:123` — an einer Zeile, die dort in Ordnung stand
         (`bash -n` sagte „ok"). **Bash liest ein Skript zeilenweise nach und
         merkt sich die Byte-Position;** wird die Datei während des Laufs
         geändert, liest der laufende Prozess an der alten Position in der
         neuen Datei weiter. Behoben in `a5788cc`: Das Skript kopiert sich
         beim Start in den Temp-Ordner und fährt die Kopie.
      3. **In der Prüfkonfiguration.** `mypy <einzeldatei>` meldete vierzehn
         Fehler, `mypy` ohne Argument — der Aufruf des Tors — null über 214
         Dateien.

      **Und eine Blockade, die keine der drei Gestalten hat und trotzdem
      dazugehört:** 3d-druck-33 hielt vierzig Zeilen an `.claude/rules/tests.md`
      zurück, um beim Merge von `b8/nach-main` keinen Konflikt zu erzeugen —
      und genau das verhinderte den Merge, weil Git eine offen geänderte Datei
      nicht überschreibt. **Zwei richtige Gründe, die sich gegenseitig
      aufhoben.** Aufgelöst, indem sie zuerst committete (`a6e786a`): Der
      Konflikt gehört in den Merge, wo beide Texte nebeneinander stehen, nicht
      in das Warten davor.

      **Und der erste Merge nach diesem Verfahren hat die Regel gleich
      mitgeliefert** (`04a9571`, 3d-druck-b8): Er ging **nicht** im geteilten
      Baum. Git verlangt bei einem Konflikt einen sauberen Arbeitsbaum — nicht
      nur saubere beteiligte Dateien —, und der Branch trug alte `main`-Stände
      mit; damit zählten **73 fremde Dateien** als beteiligt an einem Merge,
      der zwei betraf. Gelöst in einem eigenen Arbeitsbaum, danach der
      *Inhalt* der zwei Dateien herübergebracht statt der Merge-Kante.

      > Ein langlebiger Branch im geteilten Arbeitsbaum wird mit jedem Tag
      > schwerer zu mergen, weil er `main`-Stände ansammelt. Was ihn
      > mergefähig hält, ist nicht Pflege, sondern Kürze.

      Das kehrt die naheliegende Antwort um: Man denkt an häufigeres Einweben,
      und **jedes Einweben macht es schlimmer**, weil es die Zahl der
      beteiligten Dateien erhöht.

      Dazu ein Fall, der ohne den Index-Abschnitt eine Stunde gekostet hätte:
      Das Vorspulen scheiterte an einer Datei, deren Inhalt stimmte —
      `git diff HEAD` leer, aber der geteilte Index trug die Fassung von vor
      dem letzten Commit. **Git sperrte wegen einer Änderung, die es nicht
      mehr gab.**

      **Der Weg dorthin steht bereits als Werkzeug** — `tools/to_main.py` von
      3d-druck-b8 (auf `b8/nach-main`): eigener Branch je Sitzung, `origin/main`
      einweben, Tor unter dem Schloss, und **nur bei grün** nach `main`
      vorspulen. Nie mit `--force`, nie auf `main` committen, nie einen roten
      Lauf durchwinken, nie eine Konfliktauflösung erfinden. Der Satz oben über
      den falschen Erfolg stammt aus seinem Docstring.

      **Und die Regel, die daraus für einen Belegslauf folgt** — gelernt am
      23.08.2026, als eine Sitzung während eines fremden Torlaufs eine Datei
      schrieb: Sie hatte `gate_lock status` vorher abgefragt, den Lauf gesehen
      und daraus **„nicht messen" statt „nicht schreiben"** geschlossen.

      > Das Schloss serialisiert die Rechenzeit, nicht den Arbeitsbaum.
      > **Während ein Lauf als Beleg gefahren wird, schreibt niemand** — ein
      > Lauf, der einen halben Stand gesehen hat, taugt nicht als Beleg, und
      > man sieht es ihm nicht an.

      **Dieselbe Ursache beim Lesen statt beim Laufen:** `git diff` vergleicht
      gegen den **Index**, und im geteilten Baum liegen dort die Zwischenstände
      der anderen Sitzungen — ein Katalog-Diff zeigte fünf fremde Zeilen, die
      längst committet waren. `git diff HEAD` ist die Frage, die man stellen
      will: *Was unterscheidet meinen Arbeitsbaum vom letzten Commit?*
      Gefunden von 3d-druck-33.

      **Und dieselbe Ursache in ihrer teuren Form — sie wiederholt sich.** Weil
      vier Sitzungen mit privaten Indizes committen, zieht niemand den
      **gemeinsamen** Index nach. Das ist keine einmalige Aufräumarbeit,
      sondern eine Eigenschaft des Verfahrens: Am 22.08.2026 stand er zweimal
      innerhalb weniger Stunden veraltet da, beim zweiten Mal nach nur drei
      Commits (23 Dateien, 1631 Löschungen). **Wer mit privatem Index
      committet, hinterlässt einen veralteten gemeinsamen** — und der nächste,
      der ohne `-o` committet, pusht ihn. Beim zweiten Aufräumen wurde der
      Index vorher kopiert (`.git/index-tot-<zeit>`), nach der Regel, die beim
      ersten Mal gefehlt hatte.
      Am 22.08.2026 stand dort ein Schnappschuss von vor den Commits des
      Abends: `git diff --cached HEAD` meldete 27 Dateien, 87 Einfügungen und
      **1684 Löschungen** — darunter drei ganze Testdateien mit 343, 310 und
      159 Zeilen und zwei Korpusdateien. Ein einziges `git commit -a` hätte
      daraus einen Commit gemacht, und der post-commit-Hook hätte ihn sofort
      gepusht. Aufgeräumt mit `git reset` (ohne `--hard`, Arbeitsbaum
      unangetastet); gefunden von 3d-druck-b8, und zwar weil eine Datei nach
      ihrem eigenen Commit noch als `MM` im Status stand.

- [x] **Ein Test steht zwölf Minuten still, ohne zu rechnen — aufgeklärt am
      23.08.2026 (`2969086`).** Kein Fix, sondern ein Name für das Problem und
      zwei Sätze darüber, was **nicht** geht. Gefunden von 3d-druck-b8 mit
      `py-spy dump --native` an **beiden** Enden:

          Hauptthread   hält den GIL, wartet auf den Qt-Mutex
                        QComboBox::setCurrentIndex -> setModel -> connectImpl
          Nebenthread   hält den Qt-Mutex, wartet auf den GIL
                        QWidget::~QWidget -> QMenuBar::~QMenuBar
                        -> Sbk_GetPyOverride -> PyGILState_Ensure

      **Ein `QMenuBar` wird in einem Nebenthread zerstört.** Sein Destruktor
      nimmt den Qt-Mutex und braucht dann den GIL für die shiboken-Hülle; der
      Hauptthread hält den GIL und wartet auf genau diesen Mutex. Niemand tut
      das absichtlich — **Pythons Speicherbereiniger läuft in dem Thread,
      dessen Allokation gerade die Schwelle reißt.**

      **Vier Beobachtungen dieser Nacht, die einzeln keinen Sinn ergaben, sind
      damit erklärt:** warum die Läufe *stehen* statt zu stürzen (ein Deadlock
      rechnet nicht); warum `gc.collect()` nichts brachte (der Lauf im
      Hauptthread ist der harmlose); warum `undisturbed()` nicht wirkte (es
      hält den Sammler *einer Zeile* an, der Nebenthread alloziert weiter);
      und warum es das erst seit dem 22.08. gibt.

      **Der letzte Punkt gehört hierher, auch wenn er unbequem ist:** Solange
      Lambda-Ringe die Fenster hielten, sammelte sie niemand ein. Seit sie
      sterben können, können sie im **falschen Thread** sterben. Der
      Ring-Umbau war richtig und hat den Speicher flach gemacht — und er hat
      diesen Deadlock erst möglich gemacht. Wer ihn für unbeteiligt hält,
      sucht falsch.

      **Der nächste Versuch hat zwei Baustellen, nicht eine:** Zerstörung
      gehört in den Hauptthread, aber `processEvents` führt `DeferredDelete`
      nicht aus — und mit `sendPostedEvents` dazu nimmt ein zerstörtes Fenster
      den VTK-Zustand mit. Wer nur die erste löst, trifft die zweite. Beides
      steht ausführlich in `tests/conftest.py`, neben den zwei gescheiterten
      Anläufen mit `deleteLater`; erst zusammen ergeben sie die Auskunft, die
      der nächste Versuch braucht.

      **Und die Zahl, die den Wert dieses Eintrags erklärt: drei Fixes gebaut,
      drei wieder herausgenommen** — `gc.collect()`, `wait_for_all`,
      `undisturbed()`. Jeder sah überzeugend aus, jeder wurde gemessen
      widerlegt. Ein Name für das Problem und zwei belegte Sackgassen sind um
      vier Uhr morgens mehr wert als der vierte Versuch.

      Der ursprüngliche Befund, weil seine Messung weiter gilt: Gemessen am
      22.08.2026 von 3d-druck-33: `tests/test_interface_limits.py` blieb bei
      Test 23 von 30 (`test_the_tool_strip_comes_back_with_a_body`) stehen —
      **0,00 CPU-Sekunden in acht Sekunden Messung** bei 508 MB
      Arbeitsspeicher. Der Prozess rechnete nicht, er stand. Dieselbe Datei lief
      bei einer anderen Sitzung in 9,6 s durch, und einzeln nachgefahren: 30
      passed in 10,77 s, Exit 0.

      **Dreimal am selben Tag, zweimal dieselbe Datei:**

      | Datei | stand | CPU über Intervall | RAM |
      |---|---|---|---|
      | `test_interface_limits.py` | 12 min | 0,00 s | 508 MB |
      | `test_ui.py` | 27 min | 0,00 s | 423 MB |
      | `test_ui.py` | 13 min | 0,00 s über 8 s | 419 MB |

      Alle drei nach vollständigem Start, alle drei mehrere hundert Megabyte,
      alle drei ohne jede Rechenzeit. Das ist nicht mehr sporadisch beobachtet,
      sondern dreimal gemessen — und `test_ui.py` ist zweimal dabei.

      **Der Wächter in `gate_lock.py` meldet den Zustand seit `f44a44f`**, ohne
      etwas zu beenden: Ist der Halter älter als zwei Minuten und verbraucht
      sein Prozessbaum in zwei Sekunden keine Rechenzeit, sagt das Schloss es
      dem, der wartet.

      **Und am 22.08.2026 hat der Hänger eine Zeilennummer bekommen.** Das
      Werkzeug, nach dem dieser Punkt tagelang fragte, ist `py-spy dump --pid N
      --native` — es hängt sich an einen **laufenden** Prozess, braucht keine
      Vorbereitung im Code und liefert Python- und C-Stack zusammen. Installiert
      wurde es in die **Nutzer**-Umgebung und nicht in die `.venv`:
      `constraints.txt` und die Lizenzprüfung bleiben unberührt, und damit ist
      es keine neue Abhängigkeit im Sinne von Regel 22.

      Der Python-Stack, zweimal im Abstand von Sekunden abgefragt, beide Male
      identisch:

          _paint          app/ui/start_screen.py:155   <- self.setStyleSheet(...)
          __init__        app/ui/start_screen.py:139   <- die Ablagefläche
          __init__        app/ui/start_screen.py:440
          _build_central  app/ui/main_window.py:1289
          __init__        app/ui/main_window.py:837
          window          tests/test_ui.py:51          <- die Fixture

      Der native Stack nennt die Art des Stillstands:

          QWidget::setStyleSheet -> setStyle_helper -> inheritStyle
            -> notifyInternal2 -> QApplication::notify -> QLabel::event
              -> QObject::connectImpl -> QBasicMutex::lockInternal
                -> WaitOnAddress

      **Es ist ein Sperren-Deadlock beim Herstellen einer Signalverbindung, kein
      Rechenlauf und keine Rekursion.** `setStyleSheet` verschickt selbst ein
      Ereignis, Qt vererbt den Stil an die Kinder, stellt dabei zu — und
      verbindet ein Signal, während eine Sperre gehalten wird.

      **Damit erklären sich alle drei Beobachtungen auf einmal:** Es hängt an
      der **Fixture, die ein `MainWindow` baut**, nicht an einem bestimmten
      Test. Deshalb war die Testnummer jedes Mal eine andere (59 im dritten
      Fall), deshalb sind zwei verschiedene Dateien betroffen, und deshalb
      läuft dieselbe Datei einzeln durch.

      Der Rekursionsschutz an `start_screen.py:155` ist **nicht** die Ursache —
      sein Docstring beschreibt schon die halbe Sache („`setStyleSheet` löst
      selbst ein `PaletteChange` aus, und das führte zurück hierher"). Er
      verhindert die Rekursion; er verhindert nicht, dass Qt unter gehaltener
      Sperre verbindet. Gefunden von 3d-druck-b8.

      **Vierte Aufnahme, und sie nennt den Halter der Sperre.** Derselbe Hänger
      trat kurz darauf in einem anderen Torlauf auf (7,03 CPU-Sekunden, 425 MB,
      0,02 s über zehn Sekunden). Zwei Threads, beide wartend:

          Thread "MainThread" (idle)
              QMetaObject::connect -> QBasicMutex::lockInternal -> WaitOnAddress
              PySide::qobjectConnect
              __init__ (app/ui/split_bar.py:131)
              __init__ (app/ui/main_window.py:837)
              window   (tests/test_ui.py:51)

          Thread 37240 (idle)
              QObject::~QObject -> QObjectPrivate::deleteChildren
              QThread::start

      **Der Hauptthread will ein Signal verbinden; ein zweiter Thread zerstört
      gerade Qt-Objekte samt Kindern. Die Sperre hält die Objektzerstörung.**

      Zwei Dinge werden damit klarer:

      * **`setStyleSheet` ist nicht die Ursache.** Die vierte Aufnahme sitzt in
        `split_bar.py:131` — ein schlichtes `QObject::connect`, kein Stylesheet,
        keine Ereigniszustellung. Die dritte ging über
        `setStyleSheet → inheritStyle → notify → QLabel::event → connectImpl`;
        beide enden am selben Punkt. **Gemeinsam ist nur das Verbinden**, und
        die Stylesheet-Stelle war eine von vielen, die verbinden.
      * **Die Fixture-Aussage wird stärker.** Beide Stacks laufen über
        `main_window.py:837` → `tests/test_ui.py:51`, nur über verschiedene
        Widgets darunter. Es hängt am Aufbau des Hauptfensters, nicht an einem
        Widget.

      *Als Spur und ausdrücklich nicht als Befund:* Der zweite Thread tut das,
      was der Ring-Umbau vom selben Tag erst möglich gemacht hat — Qt-Objekte
      **wirklich** zerstören, wo vorher nichts freigegeben wurde. Ob das den
      Deadlock auslöst, sagt der Stack nicht; der Hänger trat auch vorher auf,
      und `QThread::start` deutet eher auf einen Arbeiter als auf einen
      Viewport.

      **Und dabei eine Messfalle, die zwei Sitzungen betraf und hier steht,
      weil sie fast ein ganzes Tor gekostet hätte.** 3d-druck-64 meldete den
      Halter als tot: `gate_lock.py` 0,125 CPU-Sekunden, darunter eine `bash`
      mit 0,016 und **kein Kindprozess**. Der Schluss („der Lauf hängt") stimmte
      zufällig, die Messung war falsch — es lief sehr wohl ein `pytest`, nur
      nicht als direktes Kind der geprüften `bash`: **Auf Windows hängt ein
      Enkel nach dem Ende eines Zwischenprozesses in einer anderen Elternkette.**
      Hätte 3d-druck-33 der Meldung geglaubt und den ganzen Lauf verworfen,
      wären 3453 bestandene Tests mit weggegangen und mit ihnen die Zuordnung,
      dass 24 Fehlschläge aus einer einzigen Zeile kommen.

      Zwei Regeln daraus, beide in `.claude/rules/tests.md`: **Der Prozessbaum
      wird über die Kette gelesen, nicht über direkte Kinder.** Und: **Ob etwas
      rechnet, sagt nur die CPU-Zeit über ein Intervall** — die Gesamtzeit eines
      wartenden Wrappers ist immer klein und sagt nichts über sein Kind. Der
      Unterschied zwischen „der Lauf ist tot" und „ein Prozess darin steht" ist
      ein ganzes Tor.

      **Das ist eine vierte Signatur neben den drei bekannten** — und die
      einzige, die *steht* statt abzustürzen. Die anderen drei enden mit
      `0xC0000409`, mit Exit 127 oder mit einer Zugriffsverletzung; diese endet
      gar nicht. Zum Nachsehen fehlt ein Python-Stapel aus einem laufenden
      Prozess, also `py-spy` — das steht nicht in `constraints.txt`, und ein
      Werkzeug ungefragt in die Umgebung zu holen ist eine Abweichung, die
      Robert entscheidet und keine Sitzung.

- [x] **Drei Fehler in `gate_lock.py` an einem Abend — und keiner davon war
      vorher zu sehen.** Am 22.08.2026 benutzten vier Sitzungen dasselbe
      Prüfschloss zum ersten Mal gleichzeitig. Was dabei herauskam:

      * **Der Rat bei Exit 75 empfahl, was man gerade getan hatte.** „Starte mit
        `--wait SEKUNDEN`" stand auch für den, der mit `--wait 3000` gestartet
        war — und führte prompt zur falschen Diagnose, das Werkzeug ignoriere
        den Schalter. Nach Regel 17 ist ein Rat, der die eigene Handlung
        wiederholt, kein Handlungsvorschlag. Behoben in `64425d3`.
      * **Der Wächter las den Prozessbaum über die Elternkette.** Auf Windows
        hängt ein Enkel nach dem Ende eines Zwischenprozesses in einer anderen
        Kette — der `pytest` war über die Kette **nicht** zu finden, über sein
        Kommando schon. Behoben in `3562e4d`; die Gegenprobe dazu fand einen
        weiteren Fehler derselben Bauart (`subprocess.Popen` startet einen
        Wrapper, dessen Kind die Arbeit tut).
      * **`_alive()` hielt beendete Prozesse für lebend.** `OpenProcess`
        liefert auch für einen toten Prozess ein Handle, solange irgendwo eines
        offen ist; erst `GetExitCodeProcess` sagt die Wahrheit. Folge: Ein
        verwaistes Schloss blockierte **19 Minuten lang alle vier Sitzungen**,
        weil `_stale()` es nicht als verwaist erkannte. Behoben in `952c669`.

      **Die neue Testart ist inzwischen fünfmal angewandt**, und vier davon
      standen schon, bevor sie in der Tabelle stand — Plattencache (zweimal),
      `detect()` gegen `detect_holes()`, `stamp()`, `check_outgoing()` und
      `user.load()`. Die Deutung dazu stammt von 3d-druck-33 und ist besser als
      der Punkt: **Die Zeile beschreibt, was gute Leute ohnehin tun, und macht
      es für die zählbar, die es nicht wissen.** Der stärkste der fünf ist
      dabei der, der *keine* Stelle prüft, sondern den Quelltext liest und
      jedes `ResultCache(` ohne `disk=` meldet — „findet auch die dritte, die
      morgen dazukommt".

      **Der Befund dahinter ist größer als das Werkzeug**, und er stammt
      ebenfalls von 3d-druck-33: *Was nur eine Sitzung benutzt, ist nicht
      geprüft, sondern nur nicht widerlegt.* Alle drei Fehler saßen seit dem ersten Tag darin und
      waren bei serieller Benutzung unsichtbar. Das ist dieselbe Aussage wie
      die Testart „Anschluss" in §35, nur für Werkzeuge statt für Zusagen.

      **Und ein Verfahren für den nächsten verwaisten Zustand:** Die Sperrdatei
      wird **kopiert** statt gelöscht (`.lock-tot-<zeit>`), damit hinterher noch
      untersuchbar ist, was dort stand. Beim ersten Mal blieb der Beleg nur
      erhalten, weil vorher gemessen worden war.

      *Bemerkenswert am dritten Fall: Der neue Wächter meldete den Zustand
      **richtig** („rechnet gerade nicht"), während `_alive()` daneben
      behauptete, der Halter lebe. Zwei Prüfungen im selben Werkzeug, die sich
      widersprachen — und die richtige war die neue. Wer nur eine davon gelesen
      hätte, hätte die falsche geglaubt.*

- [x] **Der Ordnername „3D Druck" mit Leerzeichen bricht Werkzeuge — durchgesehen am 23.08.2026, es blieb bei den beiden.** Zweimal
      am 22.08.2026, an unabhängigen Stellen:

      * `tools/link_memory.py` bildete aus `F:\3D Druck` das Kürzel
        `F--3D Druck`, während Claude Code seine Erinnerungen unter
        `F--3D-Druck` ablegt — das Werkzeug legte einen leeren Ordner an,
        verknüpfte ihn und meldete „Eingerichtet", ohne etwas zu übernehmen.
      * Das Tor-Skript zerlegte sich, sobald der Interpreterpfad absolut wurde
        (`ad2448c`).

      **Beide Male ging es nicht um einen fehlenden Anführungsstrich, sondern um
      eine Annahme**: dass ein Pfad keine Leerzeichen enthält. Sie steckt in
      jedem Werkzeug, das Pfade zusammensetzt oder zerlegt, und sie fällt nur
      dort auf, wo jemand sie ausprobiert. Wer ein Werkzeug schreibt, das einen
      Pfad anfasst, prüft es gegen **diesen** Arbeitsbaum — er ist der Ernstfall
      und liegt vor der Tür.

      **Durchgesehen am 23.08.2026, und es blieb bei den beiden.** Gesucht
      wurde nach den drei Mustern, an denen die Annahme sichtbar wird:

          Pfade in Zeichenketten gesetzt      nur Meldungstexte, kein Aufruf
          subprocess mit String statt Liste   keiner — alle übergeben Listen
          Pfade zerlegt (split, replace)      link_memory (behoben, `ad2448c`),
                                              FTP-Pfade der Website (kein
                                              Dateisystem)

      **Ein halber Fall bleibt und ist heute folgenlos:** `make_video.py`
      maskiert für den ffmpeg-Filtergraphen Backslash und Doppelpunkt, aber
      kein Leerzeichen. Er greift auf `C:\Windows\Fonts`, wo keines vorkommt —
      wer ihn auf eine Schrift in `C:\Program Files` zeigen lässt, findet es.

      **Und die Grenze der Durchsicht gehört dazu:** `grep` findet Muster, nicht
      Annahmen. Was hier gefunden wurde, sind die Stellen, an denen jemand einen
      Pfad *sichtbar* anfasst; eine Annahme, die in einer Bibliothek steckt oder
      in einem Aufruf ohne verräterisches Muster, bleibt unsichtbar. Der Punkt
      wird deshalb geschlossen, weil nichts mehr zu finden ist — nicht, weil
      bewiesen wäre, dass nichts mehr da ist.

- [x] **Der Stop-Hook meldet Zeitstempel, nicht Urheber — entschieden am 23.08.2026: er bleibt so.** Bei vier Sitzungen
      in einem Arbeitsbaum schlägt er regelmäßig für fremde Arbeit an: „Seit
      der letzten Änderung an X lief die Suite nicht" — und X gehört jemand
      anderem. Der Hinweis sagt das selbst („stammt die Änderung aus einer
      parallel laufenden Sitzung, gehört sie nicht dir"), aber die Auflösung
      kostet jedes Mal einen Blick ins Sitzungsbrett.

      **Wer den Umweg nicht geht, prüft fremden Code oder hält seine eigene
      Arbeit für ungeprüft.** Gefunden am 22.08.2026 von 3d-druck-b8, und zwar
      auf dem produktiven Weg: Der Hook meldete eine Änderung an
      `app/ui/session.py`, sie ging ins Brett — und fand dort einen Eintrag von
      3d-druck-64, der eine Absprache behauptete, die nicht stattgefunden hatte.
      Der Umweg hat also etwas gefunden, das sonst niemand gesehen hätte; er ist
      trotzdem einer.

      **Entschieden am 23.08.2026: Der Hook bleibt, wie er ist.** Drei Gründe,
      und der dritte ist der, der die Entscheidung trägt.

      *Erstens ist der Urheber nicht zuverlässig zu ermitteln.* Das Brett trägt
      Selbstauskünfte und altert — in dieser Nacht standen drei von vier
      Einträgen stundenlang veraltet da. Ein Hook, der daraus einen Namen
      ableitet, meldet „gehört 3d-druck-b8", wo längst jemand anders arbeitet,
      und **eine falsche Zuschreibung ist schlechter als keine**: Wer „nicht
      deins" liest, sieht nicht nach.

      *Zweitens ist der Umweg kurz und die Auflösung eindeutig.* `git status`
      und ein Zeitstempel klären den Fall in zehn Sekunden — das ist genau der
      Griff, der in dieser Nacht mehrfach eine Stunde gespart hat, und er wird
      durch die Übung nicht schlechter.

      *Drittens hat der Umweg zweimal etwas gefunden, das sonst niemand gesehen
      hätte* — den falschen Eintrag im Brett am 22.08. und die fremde
      Übersetzungsarbeit am 23.08. Beide Male war die Frage „wem gehört das?"
      der Anlass, und beide Male lag die Antwort nicht dort, wo sie stehen
      sollte. **Ein Hinweis, der zum Nachsehen zwingt, ist an einem Ort mit vier
      Sitzungen mehr wert als einer, der die Frage vorwegnimmt.**

      *Was stattdessen half:* Der Hinweistext sagt inzwischen selbst, dass die
      Änderung fremd sein kann und was dann zu tun ist. Das ist die billige
      Hälfte der Lösung, und sie ist gebaut.

- [x] **`test_mesh_backend` misst die Umgebung statt sein Thema — erledigt,
      geprüft am 23.08.2026.** Der Test existiert nicht mehr; die Suche nach
      `mesh_backend` in `tests/` findet nichts. Die dritte Zusicherung, die
      die Länge des Temp-Ordners **dieser Maschine** prüfte, ist damit fort,
      und die zwei davor — sie prüften den Programmtext — sind in
      `test_toolchain.py` aufgegangen.

      Ursprünglich:
      `test_the_weights_are_downloaded_through_a_short_folder` prüft, ob
      `tempfile.gettempdir()` kurz genug für den Download ist. Das ist die
      Länge des Temp-Ordners **der Maschine, auf der die Suite läuft** — nicht
      die des Kunden, um den es geht. Wer die Suite mit einem umgebogenen
      `TEMP` fährt, bekommt einen roten Test, der nichts über das Produkt sagt;
      am 22.08.2026 passierte genau das, weil die Prüf-Anleitung ihre
      Protokolle nach `$TEMP` schreibt und eine Sitzung ihn auf ihren
      Arbeitsordner setzte (100 statt 40 Zeichen).

      Die zwei Aussagen davor — geladen wird in einen kurzen Ordner, danach
      verschoben — prüfen den Programmtext und sind richtig. Die dritte prüft
      die Maschine. **Dritter Fall desselben Musters an einem Tag:** ein
      Prüfmittel, das etwas anderes misst, als man annimmt (der
      Werkzeugzeilen-Test misst die Reihenfolge des Laufs, `--fehlend` maß
      Dateilängen statt Inhalt).

- [x] **Kein Viewport wird jemals freigegeben — und die restlichen Ringe
      warten jetzt auf den Deadlock. Entschieden am 23.08.2026.**

      **Überholt, nicht erledigt** (23.08.2026). `tests/test_widget_lifetime.py`
      prüft `Viewport` und `MainWindow` und ist grün, seit der Test 41 Klassen
      baut statt 14. **Die Aussage dieses Punktes stimmt nicht mehr.**

      **Was bleibt, ist seine Warnung** — *jede aufgelöste Stelle macht ein
      Fenster einsammelbar* —, und die ist gemessen worden. `test_operation_ui`
      im eigenen Arbeitsbaum, sonst identischer Stand:

          fünf Läufe je Seite    mit 0 von 5    ohne 2 von 5
          zehn Läufe je Seite    mit 4 von 10   ohne 0 von 10
          zusammen               mit 4 von 15   ohne 2 von 15

      **Die Richtung dreht sich zwischen fünf und zehn Läufen vollständig um.**
      Die Messende hatte nach den fünf Läufen den Umbau schon halb
      zurückgenommen; fünf hätten eine Entscheidung getragen, die zehn
      widerlegen. Kein Unterschied nachweisbar — der Absturz gehört dem Baum.

      **Ein Punkt, der abgehakt wird, obwohl seine Formulierung falsch geworden
      ist, verschwindet mit seiner Warnung.** Darum steht sie hier.

      **Die Reihenfolge steht fest: erst der Deadlock, dann die verbliebenen
      Ringe. Nicht umgekehrt, und nicht parallel.** Der Grund ist die Kehrseite,
      die in derselben Nacht sichtbar wurde: *Jede aufgelöste Stelle macht ein
      Fenster einsammelbar — und ein Fenster, das eingesammelt werden kann,
      kann im falschen Thread sterben.* Solange der Deadlock offen ist, macht
      das Auflösen weiterer Ringe die Suite **instabiler**, nicht stabiler. Der
      Speichergewinn (7 MB je Fenster) ist real und wird mit Hängern bezahlt.

      **Die Zahl im Text unten stimmt nicht mehr:** Statt 59 sind es heute
      **40** `.connect(lambda … self …)`-Stellen in `app/ui/` — und das ist
      eine Obergrenze, kein Befund: Ein Ring ist es nur, wenn der Sender ein
      Kind von `self` ist. Gezählt von 3d-druck-b8, die auch dazusagt, dass
      ihre Zählung grob ist.

      Der ursprüngliche Befund, weil seine Messung weiter gilt: Gemessen
      am 22.08.2026 von 3d-druck-b8: zwanzig losgelassene Viewports und fünf
      losgelassene `MainWindow` überleben `del` und `gc.collect()` vollzählig.
      Die Ursache ist eine Zeile — `app/ui/viewport.py:1428` verband den
      Neuaufbau der Schichtansicht mit einem Lambda, das `self` stark einfängt,
      und `_layer_rebuild` ist ein `QTimer(self)`. Damit steht der Ring
      **Viewport → QTimer → Rückruf → Viewport**; er läuft über die C++-Grenze,
      und Pythons Speicherbereiniger sieht die mittlere Kante nicht.

      **Diese eine Zeile ist behoben** (weakref, mit dem Messwert im
      Kommentar): mit dem Lambda leben von zwanzig noch zwanzig, mit weakref
      keiner. Gegengeprobt am reinen Muster ohne Solidon-Code — zehn `QObject`
      mit eigenem `QTimer`, stark verbunden zehn Überlebende, schwach verbunden
      keiner.

      **Entschieden am 22.08.2026 (Robert): alle umbauen.** Die Trennung, die
      3d-druck-b8 statisch gemessen hat, trägt die Entscheidung — **33
      dauerhafte Ringe** (der Sender lebt so lang wie `self`) gegen **26
      kurzlebige** (Arbeiter, Dialoge, Animationen; der Sender geht, und mit
      ihm der Ring). Die 26 bleiben, wie sie sind: Sie sind genau das Muster,
      das die Gebietsregel vorschreibt. Elf der 33 liegen in
      `sketch_editor.py`, weitere in `main_window.py` (5), `dialogs.py` (3),
      `analysis_bar.py` (2), `install_dialog.py` (2).

      **Die Abnahme ist ein Freigabetest je Widget-Klasse, nicht die Zahl der
      umgebauten Stellen.** Wer „33 Stellen umgebaut" als Abnahme liest, hat
      nichts abgenommen: 33 richtig umgebaute Stellen plus eine neue falsche
      ergeben denselben Zustand wie vorher. Der Test fragt *wird ein
      losgelassener Editor freigegeben?* — er prüft das Ergebnis und wird rot,
      sobald jemand eine zwölfte Stelle einbaut.
      `tests/test_widget_lifetime.py` ist diese Abnahme, parametrisiert über
      die Klassen; jede neue Widget-Klasse ist eine Zeile.

      **Und die Zahl 33 ist eine Untergrenze, keine Bilanz — belegt beim ersten
      Umbau.** In `sketch_editor.py` wurden 13 Stellen umgestellt, alles grün —
      und der Freigabetest blieb rot: zehn von zehn Editoren überlebten weiter.
      `gc.get_referrers` nannte zwei weitere Halter, beide von der Bauart

          shapes_menu = QMenu(shapes_button)      # Knopf gehört self
          action = shapes_menu.addAction(label)   # Aktion gehört dem Menü
          action.triggered.connect(lambda …: self.…)

      Die Kette läuft über **drei** Ebenen — Panel → Knopf → Menü → Aktion →
      Rückruf → Panel —, und die statische Suche prüfte nur eine. `QMenu` mit
      `addAction` ist ein verbreitetes Muster; in `main_window.py` dürfte es
      mehr davon geben als im Skizzeneditor. **Genau deshalb ist die Liste
      nicht die Abnahme:** 33 abgehakte Stellen hätten hier einen Editor
      hinterlassen, der weiter nicht freigegeben wird.

      **Der nützlichste Fund des Umbaus ist aber ein anderer: `weakref` ist
      fast nie nötig.** Gemessen, bevor 33 Stellen mit Blöcken zugestellt
      wurden:

      | Verbindung | überleben |
      |---|---|
      | `connect(self.tue)` | 0 von 10 — frei |
      | `connect(lambda: self.tue())` | 10 von 10 — Ring |
      | `connect(partial(self.tue, 1))` | 10 von 10 — Ring |
      | `connect(lambda x=1: self.tue(x))` | 10 von 10 — Ring |

      **Qt hält eine gebundene Methode von sich aus schwach.** Den Ring baut
      allein das Lambda — und `functools.partial` sieht aus wie seine saubere
      Fassung und hält den Besitzer genauso fest. Der Umbau ist damit in den
      meisten Fällen `connect(self.methode)` und **kürzer** als vorher, nicht
      länger. Nur wo ein Wert aus einer Schleife gebraucht wird, bleibt eine
      schwache Bindung nötig (`app/ui/leash.py`, `weak_slot()`).

      **Die Reichweite, gemessen.** `grep -rn "\.connect(lambda" app/ui/*.py |
      grep "self\."` findet **59 Stellen**. Nicht jede bildet einen Ring — er
      entsteht nur, wenn das sendende Objekt selbst von `self` gehalten wird,
      bei einem Kind-Widget oder Kind-Timer also im Normalfall. Betroffen sind
      unter anderem `main_window.py`, `panels.py`, `sketch_editor.py`,
      `print_settings_dialog.py`. Das ist eine Änderung mit Reichweite über vier
      Gebiete und wird entschieden, nicht nebenbei gemacht.

      **Warum der Punkt schwerer wiegt als die vier Absturzpunkte:** Er könnte
      ihre gemeinsame Wurzel sein. Gemessen kostet ein nicht freigegebenes
      Fenster rund 7 MB (linear über fünf Fenster, offscreen und damit **ohne**
      VTK-Plotter); die Suite baut über siebenhundert Fenster nacheinander auf,
      und `CLAUDE.md` schreibt, sie reiße „bei über 3 GB" ab. Das ist ein
      Größenordnungsargument und **kein Beweis** — bewiesen ist, dass nichts
      freigegeben wird, was die Ursache ist und was der Fix bewirkt. Den Beweis
      führt ein Suite-Lauf mit Speicherkurve vor und nach dem Fix, unter dem
      Schloss.

      Und die Stelle, an der die Gebietsregel danebengriff: Sie warnt vor
      genau diesem Muster, nennt als Beispiel aber den Interactor — deshalb hat
      dort niemand nach einem Zeitgeber gesucht. Gefunden wurde es nicht durch
      Suchen, sondern weil ein Test zu `set_navigation` behauptete, die
      Rückrufe hielten die Ansicht nicht fest, und rot wurde: Die Rückrufe
      waren unschuldig, `gc.get_referrers` nannte den wahren Halter.
- [x] **„Keine Tests gesammelt" zählte als Fehllauf.** `suite-getrennt.sh` sucht
      seine Fensterdateien **im Text** (`grep -lE "MainWindow|Viewport|pyvista"`)
      — das ist Absicht und gut, eine neue Fensterdatei braucht damit keinen
      Eintrag. Es trifft aber auch eine Datei, die über eine Ansicht
      *schreibt*, statt eine zu bauen: `tests/test_performance.py` wanderte in
      die Fenstergruppe, weil in zwei Docstrings ein Klassenname stand. Dort
      läuft sie mit `-m "not performance"`, sammelt nichts, weil jeder Test
      darin diese Marke trägt, und pytest endet mit **Exit 5**. Das Skript
      zählt alles ungleich null als Fehllauf. Umformuliert ist der Umweg; die
      Behebung ist eine Zeile im Skript, denn „nichts gesammelt" ist keine
      Aussage über den Code. Gefunden von solidon-17, `.claude/**` ist seit dem
      Ende von c1 frei.

      **Behoben**, und zwar genau als die eine Zeile, die der Punkt vorsah:
      `zaehlt_als_fehler()` gibt für 5 dasselbe zurück wie für 0, mit der
      Begründung darüber im Skript. Gefunden von 3d-druck-3a, am Skript
      bestätigt von 3d-druck-33, nachgeprüft von 3d-druck-64.
- [x] **`test_ui.py` reißt unzuverlässig — und die Rate hängt an der Last,
      nicht an der Datei.** Die Überschrift hieß „zehn von zehn“; das ist
      **zum dritten Mal widerlegt**, jedes Mal in dieselbe Richtung. Drei
      Läufe allein unter dem Schloss am 23.08.2026 (3d-druck-33), ruhige
      Maschine:

      **Aufgegangen in Signatur B** (23.08.2026, sortiert an 24 Stapeln):
      **Das ist die Rate zu B, keine eigene Ursache.** Die Zahlen bleiben
      gültig und stehen dort: 25 bis 50 Prozent je Fensterdatei, lastabhängig.

          Lauf 1   Exit   0   257 passed
          Lauf 2   Exit   1   257 passed, 1 error   (Teardown, kein Test)
          Lauf 3   Exit 127   Absturz vor der Zusammenfassung

      **Drei Läufe, drei Ausgänge.** Die Basisratentabelle sagt „ruhig 0/3,
      unter Fremdlast 5/5“; hier war es 1/3 auf fast ruhiger Maschine.

      **Was daraus für einen Belegslauf folgt, und es ist eine Regel und keine
      Beobachtung:**

      > Bei `test_ui.py` kann der Beleg **0, 1 oder 139** zeigen, und alle drei
      > bedeuten dasselbe: Die 257 Tests bestehen. Ein Fehllauf bei genau
      > dieser Datei stoppt das Release nicht — bei einer **anderen** schon.

      **Zwei verwertbare Stapel sind dabei abgefallen**, beide neu:
      `app/ui/overlay.py:346`, `eventFilter` auf einem bereits gelöschten
      C++-Objekt (`ObjectTree already deleted`) — die erste konkrete
      Codestelle dieser Familie. Und `0xc0000374` in einem Arbeitsthread beim
      Laden aus dem Plattencache, während der GC läuft. **Ein
      Heap-Korruptionsstapel zeigt, wo der Prozess war, als der Schaden
      auffiel — nicht, wer ihn angerichtet hat;** der Plattencache steht
      darin, und daraus „der Plattencache ist schuld“ zu machen, wäre
      derselbe Fehler wie die acht Messfehler dieser Nacht.

      Ursprünglich: Gemessen am 23.08.2026 von 3d-druck-b8, unter Schloss,
      mit 42 GB freiem Speicher und zwei Python-Prozessen.

      **Die Ursache ist eingekreist:** `leash.wait_for_all` (`f1ea325`),
      gerufen aus der Aufräum-Fixture (`ff98633`). Vor diesen beiden lief die
      Datei dreimal mit 257 passed durch; danach reißt sie mit einer
      Zugriffsverletzung an `conftest.py:218` — `processEvents()` direkt hinter
      dem Aufruf. Vorher liefen Arbeiter nach dem Testende weiter und ihr
      `finished` kam nie zur Zustellung; jetzt macht die Fixture sie fertig,
      das Signal landet als `QueuedConnection` in der Schlange, und
      `processEvents()` stellt es an Empfänger zu, die es nicht mehr gibt.

      **Der methodische Teil wiegt schwerer als der Fehler.** Dieselbe Zahl
      wurde zweimal gemessen und zweimal verschieden gedeutet:

          neben einem fremden Torlauf   5/5 gerissen   -> „Fremdlast"
          unter Schloss, leere Maschine 5/5 gerissen   -> die Deutung fällt

      > Beide Male dieselbe Zahl und zwei verschiedene Deutungen; erst die
      > zweite Messung hat die erste widerlegt.

      **Die Fremdlast war nie die Erklärung — sie war die bequemere.** Und sie
      ist eine, die sich nicht von selbst widerlegt: Wer einen Abriss auf
      Fremdlast schiebt und danach nicht mehr misst, behält recht, solange er
      nicht nachsieht. Dasselbe gilt für die Abbau-Abstürze, die in dieser
      Nacht mehrfach als „die bekannten" abgehakt wurden, darunter von
      3d-druck-64.

      **Der erste Fix wirkte nicht, und das ist eine Messung:** `shiboken6.isValid`
      plus `disconnect` vor dem `wait` ergab wieder 5/5. Damit ist „Signale an
      tote Empfänger" als **alleinige** Erklärung ausgeschlossen.

      **Der Stack dieses Laufs zeigt, was die vorigen nicht hatten:**

          Current thread: Garbage-collecting
                          tests\conftest.py, line 218

      Der Absturz passiert während eines gc-Laufs, den `processEvents()`
      auslöst — **dieselbe Familie wie der Fall vom 22.08.**, gegen den
      `leash.undisturbed()` steht (gc aus, solange `processEvents` läuft;
      damals von 6/10 auf 0/10). Das erklärt auch, warum es erst seit
      `ff98633` reißt: `wait_for_all` macht die Arbeiter innerhalb der Fixture
      fertig, damit liegt an dieser Stelle mehr totes Material herum, und der
      gc findet mehr zum Abräumen. **Die Zeile hat den Absturz nicht erfunden,
      sie hat ihm Material gegeben.**

      **Für den Exit-127-Punkt darunter ändert das nichts** — 127 ist ein
      anderer Code als die Zugriffsverletzung hier, und beide Signaturen
      bleiben getrennt zu führen.

- [x] **Fensterdateien enden mit Exit 127 nach vollständigem „N passed“ —
      Ursache gefunden und behoben** (`3e6d182`, `a00d6e4`, 3d-druck-33 und
      3d-druck-b8, 23.08.2026).

          tests/test_chat_ui.py     40 passed, Exit 0     riss vorher immer
          tests/test_first_run.py   47 passed, Exit 0     riss vorher immer

      **Es war eine fehlende Schnittstelle, kein Vergessen:** Dialoge starten
      im Konstruktor einen Arbeiter, und im Test schließt sie niemand. Für
      „warte auf deinen Arbeiter“ gab es **fünf verschiedene Namen**; die
      Aufräum-Fixture kannte zwei. Sie fragt jetzt nach dem Muster, und
      `release()` steht auf allen elf Klassen — damit ist es an der Wurzel
      behoben statt in der Fixture.

      > Ein Muster, das man **abfragen** muss, ist ein fehlender Vertrag.

      Der Ein-Test-Reproduzierer läuft in **0,35 s statt 86**.

      **Was danach übrig bleibt, ist eine andere Signatur** und steht im Punkt
      darunter — Risse **vor** der Zusammenfassung. Sie hier mit aufzunehmen
      wäre der Fehler, der diesen Punkt schon drei Fassungen gekostet hat.

      Ursprünglich: inzwischen drei, und wechselnde.**

      **Belegt am 23.08.2026 über vier Läufe** (3d-druck-33):

          Lauf 1   test_chat_ui (127)   test_first_run (127)
          Lauf 2   test_chat_ui (127)   test_first_run (127)
          Lauf 3   test_pose_session (127)
          Lauf 4   test_ui (127)                        (Abbruch, zählt nicht)

      Zwei sind **konsistent** dabei, die dritte kam ohne erkennbaren Anlass
      dazu. **Damit scheidet eine Eigenschaft dieser zwei Dateien als Erklärung
      aus** — der Punkt heißt richtiger *„Fensterdateien, meistens diese
      zwei"*, und das macht ihn schwerer statt leichter.

      **Er kostet inzwischen keine Zeit mehr, ist aber ungeklärt:**
      `suite-getrennt.sh` zählt diese Läufe nicht mehr als Fehlschlag — es
      erkennt sie an einer vollständigen Zusammenfassung ohne `failed`/`error`.
      Im letzten Tor standen deshalb zwei Fehlläufe, obwohl vier Dateien mit
      127 endeten.

      **Gemessen am 23.08.2026, und die Antwort räumt den Punkt zur Hälfte
      ab** (3d-druck-33). **127 ist eine Bash-Konvention** („command not
      found") und kein Rückgabewert des Prozesses. Direkt aus Python gestartet,
      damit der Windows-Wert ankommt:

          tests/test_first_run.py   0xC0000409   47 passed   2 von 2 Läufen
          tests/test_chat_ui.py     0xC0000409   40 passed   2 von 2 Läufen

      **`0xC0000409` ist der bekannte Abbau-Absturz.** Für diese beiden
      Dateien sind die zwei Registerpunkte damit **dieselbe Sache**, und der
      Satz, der hier stand — *„127 ist ein anderer Code als die
      Zugriffsverletzung, beide Signaturen bleiben getrennt zu führen"* — ist
      widerlegt. Der Abriss ist außerdem **nicht sporadisch**: vier von vier
      Läufen, jedes Mal nach vollständiger Zusammenfassung, auch einzeln
      gefahren.

      **Und die Deutung dazu wurde zwei Stunden später von der Messenden selbst
      eingeschränkt.** 3d-druck-3a maß am selben Morgen zwei **andere** Dateien
      mit 127, die **vor** der Schlusszeile rissen — dort stand `0xc0000374`,
      Heap-Korruption, Stapel „Garbage-collecting". Dasselbe 127 in der Shell,
      ein anderer Code dahinter.

      > Nicht „127 ist `0xC0000409`", sondern: **127 sagt nichts, man muss
      > dahinter sehen.** Die Shell wirft verschiedene Windows-Rückgabewerte in
      > denselben Topf.

      Beides steht in `suite-getrennt.sh` neben der Stelle, die einen Abriss
      als „kein Fehlschlag" wertet — wer dort nachliest, *warum* 127 nicht
      zählt, findet gleich daneben, dass 127 nichts bedeutet.

      **Was bleibt, ist der Fall davor und nicht dieser:** Abrisse **vor** der
      Schlusszeile mit `0xc0000374`. Sie gehören weiter getrennt geführt — nur
      eben nicht wegen der 127, sondern wegen des Codes dahinter.

      `tests/test_chat_ui.py` (40 passed) und `tests/test_first_run.py`
      (45 passed) laufen vollständig grün durch und beenden sich dann mit 127.
      Nachgewiesen von solidon-17 im eigenen Arbeitsbaum auf HEAD — also weder
      ihre noch meine Arbeit. **Das ist eine andere Signatur als der bekannte
      Absturz beim Aufräumen**, dessen Kennzeichen in dieser Datei lautet:
      „Dieselbe Datei einzeln gefahren ist grün." Diese zwei sind einzeln nicht
      grün, sie reproduzieren jedes Mal. Entweder hat sich die wandernde dritte
      Stelle festgesetzt, oder es ist eine dritte Ursache.

      **Am 22.08.2026 kam `tests/test_pose_session.py` als dritte dazu, und das
      ändert die Aussage dieses Punktes.** Er hieß „diese zwei bestimmten
      Dateien"; mit einer dritten heißt er **„es trifft wechselnde"** — und
      damit ist die Vermutung „eine festgesetzte Stelle" schwächer geworden.
      Zwei Dateien können eine Eigenheit teilen; drei, die nichts miteinander
      zu tun haben, deuten auf etwas, das allen gemeinsam ist. Wer den Punkt
      angeht, sucht nicht mehr nach dem Besonderen an `test_chat_ui.py`,
      sondern nach dem, was jede Fensterdatei am Ende tut. Gefunden von
      3d-druck-3a in einem Torlauf.

      **Und eine Warnung an den nächsten, der es nachfährt:** Ich hatte beide
      einzeln gefahren und „grün, Exit 0" gemeldet — der Exit-Code kam aus einer
      Pipeline (`pytest … | tail -8; echo $?`) und war der von `tail`. Die
      Zahl der bestandenen Tests war echt, der Exit-Code nicht. Wer diesen Punkt
      prüft, schreibt die Ausgabe in eine Datei und liest sie danach.

- [x] **Ein Absturz vor der Schlusszeile ist eine dritte Signatur.**
      `test_selection.py` ist dafür ein **Kandidat** als Messstelle — und
      ausdrücklich keine gesicherte Grundlage. Zwei Messungen vom 23.08.2026
      nebeneinander:

      **Aufgegangen in Signatur B** (23.08.2026, sortiert an 24 Stapeln):
      Dieselbe Sache wie *Fünf Fensterdateien reißen vor ihrer
      Zusammenfassung*, nur anders formuliert. Dort steht die Signatur.

          3d-druck-3a   im eigenen Torlauf     Riss bei 18 von 20 Punkten,
                                               einzeln grün
          3d-druck-33   mit test_analysis_ui   allein     3/3 grün
                        daneben, drei Läufe    kombiniert 2/3 grün,
                                               1/3 gerissen (0xc0000005,
                                               bei 65 Punkten)

      **Bei 1/3 ist ein grüner Lauf nach einem Fix genau so viel wert wie
      vorher, nämlich nichts.** Die Empfehlung, hier ließe sich „in zwei Läufen
      statt in zwanzig" bewerten, trägt damit nicht.

      **Die beiden Messungen widersprechen sich dabei nicht** — sie sind in
      verschiedenen Lagen entstanden (anderer Nachbar im geteilten Lauf), und
      der dritte Lauf der zweiten fiel mit einer fremden Änderung an
      `brep/features.py` zusammen und ist als Datenpunkt nicht sauber. Was sie
      zeigen, ist: **Die Stelle ist nicht ohne Weiteres übertragbar.**

      **Wer den vierten Deadlock-Anlauf macht, misst sie zuerst in seiner
      eigenen Lage nach.** Das kostet sechs Läufe und erspart eine Bewertung,
      die auf Sand steht.

      **Warum das hier so ausführlich steht:** Die Zeile stand eine halbe
      Stunde lang als „reproduzierbare Messstelle" im Register. Sie kam als
      Empfehlung von 3d-druck-33, die eine fremde Beobachtung ungeprüft
      weitergereicht hat — und 3d-druck-64 hat sie ungeprüft eingetragen.
      **Zwei Sitzungen, eine Zahl, kein einziger eigener Fall.** Die Regel
      dagegen stand zu dem Zeitpunkt schon in `.claude/rules/tests.md`, von
      derselben Hand geschrieben, die sie gebrochen hat:

      > Wer eine Zahl weitergibt, gibt das Muster mit — wer eine bekommt,
      > prüft sie an einem Fall, von dem er weiß, wie er ausgehen muss.

      Dazu `test_sculpt_session.py`, das nach 23 Punkten mit einer
      Zugriffsverletzung in `app/ui/session.py:112` reißt.

      Ursprünglich:
      `tests/test_ui.py` riss am 22.08.2026 in einem von vier Läufen bei
      **95 Prozent** mit Exit 139 ab — Zugriffsverletzung in `conftest.py:178`,
      also in `application.processEvents()` beim Aufräumen einer
      Fensterprüfung. Dreimal danach wiederholt: 255 grün, Exit 0, jedes Mal.
      Gemessen von solidon-17.

      **Warum das nicht der bekannte Absturz ist:** Dessen Kennzeichen in
      dieser Datei lautet „N passed, dann Absturz" — die Schlusszeile steht
      da, und wer sie liest, hält den Lauf für vollständig. Dieser hier stirbt
      **vor** ihr. Ein Lauf ohne Zusammenfassung sieht nach „abgebrochen" aus
      und nicht nach „abgestürzt", und die beiden verlangen Verschiedenes: Der
      eine wird wiederholt, der andere untersucht. Damit stehen drei
      Signaturen nebeneinander — 127 nach vollständigem Lauf (zwei Dateien,
      reproduzierbar), `0xC0000409` nach der Schlusszeile (bekannt), und 139
      mitten darin (nichtdeterministisch, einer von vier).

- [x] **Nichts hindert eine Operation daran, die Uhr zu lesen.** §15.1 verlangt,
      dass die Auswertung eine reine Funktion aus Stack, Quellen, Parametern,
      Profilen und Startwerten ist. Für den **Zufall** ist das durchgesetzt:
      `operation_hash` nimmt `operation.seed`, Regel 9 verlangt einen
      gespeicherten Startwert, und der Determinismustest prüft es. Für alles
      andere, was von außen kommt, ist es eine Absichtserklärung — eine
      künftige Op, die `datetime.now()`, eine Umgebungsvariable oder eine Datei
      außerhalb des Projekts liest, wäre keine reine Funktion, und **kein Test
      würde es merken**.

      Aufgefallen ist es beim Plattencache, aber es gehört nicht dorthin: Eine
      Op, die die Uhr liest, verstößt gegen Regel 9, unabhängig von jeder
      Cache-Ebene. Der Ort ist deshalb `tests/test_registry_consistency.py`,
      wo schon steht, dass eine nicht-deterministische Op einen Startwert
      führen muss. Gefunden von solidon-17 und solidon-43.

      **Gebaut — und die Reichweite ist gemessen, nicht gewählt.**
      `test_no_operation_reads_the_clock_the_environment_or_the_machine`
      verfolgt den Aufrufgraph von jeder Operation und jedem Baustein aus und
      meldet jede Stelle, die Uhr, Umgebung, Arbeits- oder Nutzerverzeichnis,
      Rechnernamen oder den angemeldeten Nutzer liest. Drei Schnitte standen
      zur Wahl, alle drei gefahren: nur die 24 Module, die Operationen halten
      (0 Treffer, sieht aber keine Hilfsfunktion zwei Ebenen tiefer); der ganze
      Graph durch `app.` (574 Funktionen, **15 Treffer — und alle fünfzehn
      berechtigt**: `perf_counter` in `backends/openscad` misst die Laufzeit
      eines Unterprozesses, `os.environ` und `Path.home` in `discover` und
      `paths` suchen das fremde Werkzeug und den Nutzerordner); der Graph durch
      die **rechnenden** Module (503 Funktionen, 0 Treffer). Genommen ist der
      dritte, weil nur er ohne Ausnahmeliste auskommt — eine Prüfung mit
      fünfzehn Ausnahmen prüft nichts mehr. Der Satz dazu: Wo gerechnet wird,
      gibt es keinen Grund, die Uhr zu lesen; wo ein fremdes Werkzeug gesucht
      und gestartet wird, gibt es ihn.

      **Die Gegenprobe hat sich zweimal gelohnt, und beide Male hätte kein
      Nachdenken es gefunden.** `test_the_purity_check_would_notice` schickt
      vier Funktionen durch die Prüfung, die die Uhr lesen, und eine, die es
      nicht tut. Fassung 1 fand **keine** der vier: Sie sah nur in den
      Namensraum des Moduls, und ein `import datetime` innerhalb der Funktion
      legt dort nichts ab — die im Bestand übliche Form. Fassung 2 fand drei:
      `Path.home()` entkam, weil `pathlib.Path` seit Python 3.13 als aus
      `pathlib._local` stammend gemeldet wird. Der Bestand war in allen drei
      Fassungen grün; ohne die Gegenprobe wäre er es aus dem falschen Grund
      geblieben. Sie bleibt deshalb stehen und prüft nicht den Code der
      Anwendung, sondern das Werkzeug darüber.

      Aufgelöst wird über den Namensraum und die `import`-Anweisungen, nicht
      über den geschriebenen Namen: `from time import monotonic as tick` fällt
      damit genauso auf wie `time.monotonic()`. `random` und `uuid4` stehen
      bewusst nicht in der Liste — Regel 9 und der Determinismustest decken den
      Zufall, und eine zweite Stelle, die dasselbe prüft, driftet von der
      ersten weg.


## Der Changelog schickte den Kunden ins Handbuch, und dort war nichts (22.08.2026)

Das Update-Fenster war fertig gebaut — Punkte in sechs Sprachen, Prüfsumme,
Abbruch, alles. Nur stand in einem der acht Punkte etwas, das es nicht gibt.
Dazu kam die Umstellung von „Fassung" auf „Version", und beim Durchgang durch
alle Gebiete fielen drei weitere Sachen auf, von denen zwei die Suite rot
gehalten hätten.

### Behoben: der achte Punkt versprach eine Handbuchseite

- [x] **„Das Handbuch hat eine Übersicht aller Tastenkürzel bekommen" — hat es
      nicht.** Die Übersicht ist ein Dialog *in der Anwendung*: Hilfe →
      „Tastenkürzel …", Taste `?`, `app/ui/shortcuts_window.py`, erzeugt aus
      dem Register. Im Handbuch stehen Kürzel nur einzeln bei jeder Operation
      („· Kürzel X" im Referenzteil); eine Übersicht gibt es dort nicht, und
      `website/handbuch.html` kennt weder `Strg+Tab` noch `Alt+1` bis `Alt+8`.

      Der Punkt hätte den Kunden an eine Stelle geschickt, an der er nichts
      findet — und zwar in allen sechs Sprachen gleichzeitig. Neu formuliert,
      ohne Pfeil: `→` bricht in jeder Umgebung, die nicht UTF-8 spricht, und
      ein Kundentext wird auch vorgelesen. `website/version.json` nachgezogen,
      ohne die Paketliste anzufassen — `make_download.py` ohne Paketdateien
      **leert den Kasten**, und die Pakete liegen nicht im Repository.

      Die anderen sieben Punkte stimmen. Gegengeprüft wurde der mit der
      konkreten Zahl: `FIELDS` in `app/ui/print_settings_dialog.py` hat genau
      sechsundfünfzig Einträge, und `tests/test_print_settings_ui.py` hält das
      fest.

### Behoben: jede Neuerzeugung der Rechtstexte nahm den Sprunglink heraus

- [x] **`tools/make_legal.py` kannte ihn nicht** (WCAG 2.4.1). „Neunundzwanzig
      Seiten, und auf keiner kam die Tastatur an der Kopfzeile vorbei"
      (`91494ca`) zählte EULA, AGB und Widerruf zu den *von Hand gepflegten*
      Seiten und trug `<a class="skip">` dort im Quelltext nach — nur werden
      die drei erzeugt. Der nächste Lauf des Erzeugers nahm ihn wieder heraus,
      zusammen mit dem `id="content"`, auf das er zeigt.

      Genau das passierte hier: `make_legal.py` lief wegen der Wortumstellung,
      und `tests/test_website.py::test_every_page_lets_the_keyboard_skip_the_header`
      wurde rot — mit drei Zeilen, an denen sich am Inhalt nichts geändert
      hatte. Der Erzeuger schreibt ihn jetzt selbst; zweiter Lauf erzeugt
      dieselbe Datei.

### Behoben: zwei Paketbeschreibungen standen noch auf 0.1.1

- [x] **Aus dem geholten Stand mitgekommen, nicht von hier.**
      `packaging/macos-distribution.xml` und die drei Linux-Beschreibungen
      trugen `0.1.1`, während `app/branding.py` auf `0.1.2` steht — zwei rote
      Tests in `tests/test_packaging.py`, die genau dafür gebaut sind („eine
      erzeugte, eingecheckte Datei veraltet still"). Neu erzeugt mit
      `--files`, wie die Meldung des Tests es sagt. Dabei fiel auf, dass
      `packaging/install.sh` denselben Drift hatte, nur ungeprüft: Der Satz im
      Werkzeug sagte längst „Version", die erzeugte Datei noch „Fassung".

### „Fassung" heißt jetzt „Version"

- [x] **93 Stellen gefunden, 79 umgestellt, vierzehn stehen mit Grund.**
      „Kurzfassung", „Zusammenfassung",
      „Langfassung" und „Einfassung" sind eigene Wörter und bleiben; umgestellt
      wurde, was einen Ausgabestand meint — auch „Programmfassung",
      „Paketfassung" und „Sprachfassung".

      Drei Ausnahmen mit Grund: Der Kopf der drei Rechtstexte („Stand: 8.
      August 2026 · Fassung 1.0") meint die Fassung *des Dokuments*, nicht des
      Programms, und „Diese Bedingungen gelten in der bei Vertragsschluss
      geltenden Fassung" ist eine stehende Formel. Die fünf `.eml` unter
      `marketing/versand/` bleiben ebenfalls: Sie sind der Beleg dessen, was
      an die Redaktionen ging, kein Text, den man nachbessert.
      **Nachtrag vom selben Tag:** Robert hat entschieden, dass das
      Presse-Material ganz wegfällt. Die fünf `.eml` sind damit gelöscht, und
      die Begründung oben ist gegenstandslos — sie war richtig, solange die
      Dateien blieben. Sie stehen weiter in der Historie; die Sichtbarkeit des
      Repositorys ist inzwischen privat.

### Das Tor läuft am Stück nicht mehr durch, und das stand nirgends

- [x] **`pytest -q` hängt.** Zweimal angesetzt, zweimal bei 83 % stehen
      geblieben — 2,9 GB, kaum noch CPU, kein Fortschritt. Der Hänger sitzt in
      `tests/test_style.py`, hinter über siebenhundert VTK-Fenstern in einem
      Prozess.

      Die CI löst das seit dem 12.08.2026 mit je einem Prozess pro Fensterdatei,
      und es gibt ein Skript dafür — `suite-getrennt.sh`, ungetrackt, unter
      `.claude/.state/`. In `CLAUDE.md` steht weiter `pytest -q` mit dem Satz
      „Diese vier sind zusammen das Tor", ohne ein Wort davon. Ein frischer
      Klon hat den einzigen Weg nicht, auf dem die Suite durchkommt.

      *Beides erledigt am 22.08.2026: `CLAUDE.md` beschreibt den geteilten Lauf
      samt `-m performance` und den zwei Fallen (Exit-Code statt Schlusszeile,
      Abriss beim Abbau ist kein roter Test), und `.claude/.state/` ist
      eingecheckt — das Skript reist jetzt mit.*

      Geteilt gefahren ist der Stand grün: Sammellauf Exit 0, 23 von 26
      Fensterdateien Exit 0, Leistungstests 19 passed. **Jeder Test ist grün.**

- [x] **Drei Fensterdateien stürzen beim Abbau ab, nachdem sie grün gemeldet
      haben.** `test_chat_ui.py` (40 passed) und `test_first_run.py` (45 passed)
      enden mit `0xC0000409`, `test_ui.py` mit einer Zugriffsverletzung. Das
      Skript zählt sie als „Läufe mit Fehler: 3" und gibt Exit 3 — ein Tor, das
      rot meldet, obwohl kein Test rot ist.

      Gegengeprüft, dass es nicht an dieser Arbeit liegt: `test_first_run.py`
      stürzt mit dem Stand aus `HEAD` genauso ab (dort zusätzlich mit dem
      Fehlschlag, der hier behoben ist), und `test_chat_ui.py` ist gar nicht
      angefasst worden. Einzelne Tests derselben Datei laufen sauber durch;
      beide Hälften stürzen. Es ist der Abbau, nicht ein Test.

      `0xC0000409` ist dasselbe Bild, das „Die neuen Tests fanden einen alten
      Absturz" als „Exit 127, kein Faulthandler-Dump" beschreibt. Dort steht
      auch, was offen blieb: „`_on_agent_done` und der Split-Arbeiter lassen
      ihre Referenz genauso los; dort hämmert nur niemand." `test_chat_ui.py`
      hämmert dort.
      **Berichtigt am selben Tag: „drei Dateien" war zu genau.** `solidon-b0`
      hat den geteilten Lauf am Abend wiederholt und jeden Fehlschlag einzeln
      nachgemessen:

      | Datei | im Sammellauf | einzeln nachgefahren |
      |---|---|---|
      | `test_chat_ui.py` | 40 passed, Exit 127 | dasselbe — reproduzierbar |
      | `test_first_run.py` | 45 passed, Exit 127 | dasselbe — reproduzierbar |
      | `test_sculpt_session.py` | Segfault 139 | **viermal Exit 0**, 31 passed |
      | `test_ui.py` | **Exit 0** | Exit 0 |

      Damit stimmt die Zahl, aber nicht die Namensliste: **Zwei sind
      reproduzierbar, die dritte wandert.** `test_ui.py` — oben namentlich
      genannt — lief an diesem Abend sauber, und an seiner Stelle riss
      `test_sculpt_session.py`. Die Menge bleibt bei drei, die Stelle nicht.

      Der Fehler war meiner und ist der Sorte nach derselbe, den wir heute
      dreimal gefangen haben: Aus **einem** Lauf eine feste Liste zu machen.
      Wer die drei Namen liest und morgen `test_slots.py` reißen sieht, hält es
      für einen neuen Fehler — dabei ist es der alte an einer anderen Stelle.

- [x] **Falsch gezählt, und zwar dreimal.** Zwischenstände wurden mit
      `grep -cE "^(FAILED|ERROR)"` gemessen. Das trifft nur die
      Zusammenfassungszeilen, und die schreibt pytest erst am **Ende** — ein
      laufender Lauf meldet damit immer null. Zwei Fehlschläge standen die
      ganze Zeit als `F` im Fortschritt. Gezählt wird ab jetzt über die
      Fortschrittszeichen, und die Zusicherung ist der Exit-Code, nicht eine
      Zeile im Text.

### Nachgezogen

- [x] `.claude/rules/tests.md` nannte `test_way_one/two/three.py` und „die drei
      Hauptwege". Es sind vier — `test_way_four.py` gibt es seit `cb8d2f9`,
      und `AGENTS.md` sagt es richtig („die vier Wege aus Bauplan §2.2").

### Was offen bleibt

- [x] **`CLAUDE.md` verwies auf eine Spalte, die es nicht gibt.** Dort stand,
      die Schlusstabellen *beider* Bedienkonzept-Dateien trügen seit dem
      19.08.2026 eine Spalte mit dem Stand. Für `bedienkonzept-ueberblick.md`
      stimmt das; die Schlusstabelle von `bedienkonzept-funktionen.md` hat
      weiter nur `# | Regel | Wo umzusetzen | Aufwand`, und der Stand steht in
      einer *zweiten* Tabelle darunter. Das Dokument vermerkt den Irrtum selbst
      („Die Tabelle nennt den Ort, nicht den Stand — und `CLAUDE.md` verweist
      auf sie, als nenne sie den Stand").

      **Berichtigt am 22.08.2026**, im Zuge des Dokumentumbaus und auf Roberts
      Wort: Der Satz nennt jetzt beide Orte getrennt — im Überblick die vierte
      Spalte, bei den Funktionen die eigene Tabelle darunter — und schließt mit
      der Regel, die den Irrtum verhindert: wer den Stand sucht, sucht die
      Tabelle mit der Spalte „Stand" und nicht die letzte der Datei.

      Der Fund kam aus der Nebensitzung, die Änderung aus dieser. Nachgeprüft
      wurde er unabhängig, bevor er umgesetzt wurde — eine fremde Sitzung ist
      für Roberts Anweisungsdatei keine Grundlage, auch bei richtigem Befund.

- [x] **Die Korrektur war lokal.** `website/version.json` lag richtig im
      Arbeitsbaum; was der Kunde abfragt, ist die Datei auf dem Server. Bis
      `tools/upload_website.py` lief, las jedes Update-Fenster weiter den
      alten achten Punkt.

      **Hochgeladen am 22.08.2026 und gegengeprüft:** Die Datei unter
      `https://solidon3d.de/version.json` ist mit der lokalen identisch, und
      der achte Punkt nennt jetzt das Hilfemenü statt des Handbuchs. Die drei
      Pakete, die sie ankündigt, liegen mit passender Größe auf dem Server.

      **Und dabei kam heraus, dass es nicht bei dieser einen Datei geblieben
      war:** Acht weitere standen veraltet oben, darunter AGB, EULA und
      Widerrufsbelehrung. Der Abgleich konnte sie nicht sehen — er verglich
      Dateigrößen, und „Fassung" ist so lang wie „Version". Der eigene Punkt
      dazu steht unter „Das Fundament der Wahrnehmung".

---

## Zwei Menüzeilen, die dasselbe sagten, und zwei, die dasselbe taten (23.08.2026)

Vier Funde aus derselben Frage — *was liest ein Kunde im Menü, und was
bekommt er dann?* Drei davon waren Namen, einer war eine Operation zu viel.
Alle vier gehen auf Roberts Satz zurück: „mach es aus Kundensicht perfekt, du
sollst alles was du tust immer perfekt aus kundensicht machen."

- [x] **Zwei Einträge hießen beide „vernetzen".** *Neu vernetzen* und
      *Gleichmäßig vernetzen* standen untereinander. Der Unterschied ist echt
      und stand nur im doc-Satz: Das eine **teilt** lange Kanten und lässt die
      Form exakt, das andere teilt **und legt zusammen**, wodurch die Form sich
      verschiebt. Wer den Satz nicht aufklappt, wählt eine der beiden und
      hofft. Jetzt heißen sie *Kanten verfeinern* und *Dreiecke angleichen* —
      der Titel allein trennt sie. `3910583`.

      **Ein umbenannter Titel fasst mehr an, als man denkt: elf Stellen.** Fünf
      Texte nannten ihn im Fließtext (Reparaturkette, Handbuch,
      Erzeugungshinweis, Palettentext, Beispielskript), fünf Kataloge in beiden
      Richtungen — Schlüssel **und** Wert, denn die Übersetzung nennt den
      Menünamen in der Zielsprache —, dazu das Handbuch in sechs Sprachen.

      **Die letzte Stelle lag außerhalb von `app/`**, und sie hat zwei
      Nachbesserungen gekostet: `tools/make_examples.py` liest der Einsammler
      über `EXTRA_SOURCES` mit. Ein Beispielskript, das einen Menünamen nennt,
      ist auch ein Oberflächentext. Wer nur `app/` durchsucht, hält sich für
      fertig und ist es nicht.

- [x] **Neun tote Katalogschlüssel aus einer fremden Textdurchsicht.** Der
      Quelltext sagt seit `62ac566` „exakter Körper" statt „B-Rep-Körper"; die
      alten Einträge blieben stehen und machten `test_every_text_is_translated`
      in **allen fünf Sprachen** rot — am `orphaned`-Zweig, nicht am fehlenden.
      Eine Sitzung, die kurz darauf ein Release bauen wollte, stand vor einem
      roten Tor und suchte bei sich.

      **Die Lehre ist die Reihenfolge, nicht der Fehler:** Ein Titel ändern
      heißt Kataloge in **beide** Richtungen nachziehen, und zwar im selben
      Commit. Der Test prüft beides — deshalb fällt ein halber Nachzug nicht
      dem Autor auf die Füße, sondern dem Nächsten.

- [x] **`split_plane` war `split_pinned` mit null Stiften.** Zwei Operationen,
      die dasselbe rechnen — gemessen an `cube_clean.stl` und nicht vermutet:
      gleiche Hälften (4800 und 3200 mm³), gleiche Namen, gleiche Merkmale,
      gleiche Befunde. Robert hat entschieden, dass sie zusammengehen; die
      Migration 10 → 11 setzt `pins = 0`.

      **Sie war schon halb zusammengelegt, und das war das eigentlich
      Interessante.** Über `MENU_TWINS` verschwand *An Ebene teilen* aus dem
      Menü — in der **Befehlspalette** stand es weiter, direkt neben *Teilen*.
      Gemessen: 87 Palettenzeilen, zwei davon dasselbe. Derselbe Fehler eine
      Ebene tiefer. `MENU_TWINS` versteckt das Menü und sonst nichts; ein
      Zwilling, der keinen eigenen Umschalter braucht, gehört deshalb nicht in
      die Tabelle, sondern in eine Migration.

      **Die Null muss ausdrücklich in der Datei stehen.** Das Feld
      *Passstifte* hat als Vorgabe **zwei**. Wer den Parameter in der Migration
      wegließe, bekäme aus einem alten Projekt ein verstiftetes Teil — zwei
      Zapfen und zwei Bohrungen, die dort nie waren. Der Test misst deshalb
      Volumen und Merkmale, nicht den Operationsnamen: Volumen allein fängt
      einen Zapfen samt Gegenbohrung nicht, die beiden heben sich fast auf.

- [x] **`brep_to_mesh` zeigte einen Dialog aus einem Satz und einem leeren
      Aufklapper.** Die Operation hat genau ein Feld — *Feinheit* —, und das
      stand hinten. Nichts zu entscheiden, und trotzdem OK klicken. Dabei ist
      es genau das Feld, das später alles bestimmt: Der doc-Satz nennt die
      Umwandlung selbst unumkehrbar („die Kanten sind danach fort"). Wer mit
      0,05 mm umwandelt und danach merkt, dass es zu grob war, muss den Schritt
      zurücknehmen — und dafür muss er wissen, dass es die Einstellung gibt.
      Gefunden von 3d-druck-b8 beim Vermessen aller 82 Dialogvorderseiten,
      gebaut hier.

- [x] **Die Website nannte 87 Operationen, das Register führt 86.** Achtzehn
      Stellen in sechs Sprachen, gefunden vom eigenen Test und nicht von Hand.
      Ersetzt wurde mit **demselben Ausdruck, den der Test benutzt** — und
      unter Auslassung der Inline-SVGs, die erfundene Beispielzahlen tragen.
      Eine Zahl auf einer Verkaufsseite ist eine Zusage; wer eine Operation
      entfernt, hat sie zurückzunehmen.

---

## Ein Deadlock, der keiner war — und sieben Pakete statt einem (23.08.2026)

Der Registerpunkt hieß „Ein Importzyklus in `app/core/scene`" und nannte drei
gemessene, widerlegte Ansätze. Die Messungen stimmten alle. Die **Deutung**
nicht, und deshalb war jeder der drei Ansätze folgerichtig wirkungslos.

- [x] **Es ist kein Zyklus, sondern eine Lock-Inversion.** Der Punkt nannte den
      Rückimport `from app.core.scene import expressions` als Ursache. Der ist
      jetzt weg — `expressions` liegt unter `app/core/`, wo es ohnehin
      hingehört: `geom` und `sketch` benutzen es auch, und ein Ausdrucksauswerter
      ist keine Szenensache. **Der Deadlock blieb, fünf von fünf.**

      Was ihn auslöst, sind zwei Wege zu demselben Namen, die ihre Locks in
      umgekehrter Reihenfolge nehmen:

          from app.core.scene import History          # erst Paket, dann Untermodul
          from app.core.scene.history import History  # erst Untermodul, dann Paket

      Sequenziell löst Python das auf. Zwei Threads verklemmen sich.

- [x] **Es war nicht ein Paket, sondern sieben.** Die Gegenprobe stand schon in
      der Roadmap — `geom`, `perceive` und `knowledge` waren sauber — und sie
      wurde als „kein Rückimport" gelesen. Der wahre Unterschied ist ein
      anderer: **ihre `__init__` bestehen aus einer Zeile Docstring.** Wer
      danach sucht, findet:

          scene registry sketch agent brep activation knowledge.parts

      Alle sieben deadlocken, gemessen. Und `brep` zeigte beim ersten Lauf
      „sauber" — sechs weitere Läufe rissen alle. Einmal messen reicht auch
      hier nicht.

- [x] **Fünf sind behoben** (`app/core/lazy.py`): Die Namen werden erst beim
      Zugriff geladen (PEP 562), damit ist `__init__` fertig, bevor das erste
      Untermodul lädt — die beiden Locks werden nie gleichzeitig gehalten.

      **Ein `__getattr__` auf Modulebene genügt dafür nicht**, und das kostete
      34 rote Tests: Es läuft nur, wenn das Attribut **fehlt**. Sobald irgendwer
      `app.core.scene.evaluate` importiert, setzt Python das *Untermodul* als
      Attribut — und es heißt genauso wie die Funktion darin. Ergebnis:
      `TypeError: 'module' object is not callable`. Dass das vorher nie auffiel,
      lag am eifrigen `from …evaluate import evaluate`, das es überschrieb,
      solange es als Letztes lief. **Also dieselbe Abhängigkeit von der
      Importreihenfolge, die schon den Deadlock verursacht hat** — nur an einer
      anderen Stelle sichtbar. Es braucht eine Modulklasse mit
      `__getattribute__`.

- [x] **Der Test prüft jedes Kernpaket, nicht `scene`.** Er hat mich zweimal
      korrigiert, und beide Male war die Korrektur mehr wert als der Test:

      **Erstens war er grün an einem Paket, das nachweislich deadlockt.** Der
      zweite Thread importierte das Paket selbst, um an seine Untermodule zu
      kommen — damit war es geladen, bevor der Wettlauf begann. Aufgefallen nur
      durch die Gegenprobe (Ausnahmeliste leeren, muss rot werden). Alles
      Nachschlagen passiert jetzt vor dem ersten Thread.

      **Zweitens fand er danach ein siebtes Paket**, das mein eigener Handscan
      übersehen hatte: `knowledge.parts` ist ein Unterpaket, und ich hatte nur
      die direkten Kernpakete durchgesehen. Ein Test über die erhobene Menge
      statt über eine getippte Liste — genau der Unterschied, den
      `.claude/rules/tests.md` beschreibt.

- [ ] **Zwei Pakete lösen den Deadlock noch nicht auf**, und beide aus
      demselben Grund: Bei ihnen wäre es ein **Verhaltenswechsel** und kein
      Strukturfix.

      **`app.core.activation`** — sein `__init__` ist keine Liste von
      Re-Exporten, sondern 223 Zeilen Code an der Lizenzgrenze. `store` und
      `integrity` stehen dort als Modulnamen, und der Code darunter benutzt sie
      (`integrity.intact()`, `store.days_left()`). Sie zu verzögern heißt, die
      Importe in die Funktionen zu ziehen — an einer Stelle, deren
      Ladereihenfolge Teil der Sicherheitszusage ist (`.claude/rules/kern.md`,
      „Die Lizenzgrenze"). Das gehört zusammen mit
      `tests/test_licence_boundary.py` gemacht, nicht nebenbei.

      **`app.core.knowledge.parts`** — dort **ist** der Import die
      Registrierung. Die fünf Modulimporte (`fasteners`, `mechanics`,
      `mounting`, `structure`, `testbodies`) füllen das Bausteinregister, und
      `bootstrap.load_operations` verlässt sich darauf; der Docstring sagt es
      ausdrücklich zu. Verzögert wären sie wirkungslos — das Register bliebe
      leer, und `insert_*` verschwände. Der Weg wäre eine Ladefunktion wie
      `load_operations`, also eine geänderte Zusage nach außen.

      `tests/test_core_isolation.py` führt beide Namen in `KNOWN_OPEN`, jeden
      mit seiner Begründung. Wer einen behebt, streicht ihn dort — dann prüft
      der Test ihn mit.

---

## Sechs Sekunden schwarzes Fenster, und ein Kunde, der es für einen Absturz hielt (23.08.2026)

Robert hat die Anwendung gefahren, Weg 1 geöffnet und gemeldet: „wir bleiben
im startbildschirm stehen, er wird nicht richtig dargestellt bei auswahl von
beispielprojekt weg 1 stürzen wir ab" — und kurz darauf „jetzt stürzen wir
sofort ab".

**Es war kein Absturz.** Das Protokoll sagt beide Male
`Solidon3D 0.1.4 ended normally`; das Bildschirmfoto zeigt ein Fenster mit
Menüleiste, Werkzeugleiste und Statusleiste, dazwischen schwarz — kein
Objektbaum, keine Parameterleiste, kein Verlauf —, unten rechts ein laufender
Fortschrittsbalken mit *Abbrechen*.

    21:59:30  opened project weg1-halterung-anpassen.p3d
    21:59:36  letzte Rechnung                      <- sechs Sekunden
    21:59:38  ended normally

**Der Befund zerfällt in zwei Hälften, und sie gehören getrennt aufgeschrieben**
(3d-druck-33): Die eine ist die Ladezeit, die andere das Bild währenddessen.
Wer sie zusammenschreibt, hakt beide ab, sobald die Zeit sinkt — und ein
Fenster, das drei Sekunden lang wie abgestürzt aussieht, ist immer noch eines,
das wie abgestürzt aussieht.

- [x] **Ein Fenster, das lädt, sieht aus wie eines, das abgestürzt ist**
      (§2.8). Menüleiste und Statusleiste stehen, die Fläche dazwischen ist
      schwarz. Genau daran erkennt jeder Nutzer ein hängendes Programm, und
      Robert hat es zweimal so gelesen — beim zweiten Mal, ohne den ersten
      Versuch abzuwarten.

      **Behoben (3d-druck-43, 26.08.2026), auf echten Bildschirmfotos
      nachgestellt und belegt.** Es waren nie sechs Sekunden schlechter
      Anzeige — es war gar keine: Das native VTK-Fenster liegt auf dem
      Bildschirm über jedem gemalten Geschwister, und bis zu seinem ersten
      Render (der erst mit dem ersten Ergebnis kam) standen dort alte
      Pixel — der Startbildschirm oder Schwarz. Der Ladeschleier stand
      unsichtbar **darunter**; `widget.grab()` malte ihn und log damit, nur
      `grabWindow` (der echte Bildschirm) zeigte Roberts Bild. Jetzt
      verbirgt das Fenster die Ansicht, solange der Schleier steht
      (`loading.py` ``appeared``/``ended`` → `middle_stack`), und beim
      Öffnen eines Projekts mit Schritten erscheint der Schleier sofort
      statt nach 200 ms (``at_once``). Karten und Tour stehen von Anfang an;
      das erste Bild der Ansicht ist das fertige Modell. Der Balken unten
      bleibt, wo er war.

      Der Fortschrittsbalken unten rechts widerspricht dem zwar, aber er steht
      in der Statusleiste am unteren Bildrand, während der Blick auf der
      schwarzen Fläche in der Mitte liegt. **Gehört b8** (Panels und
      Ansichtsaufbau).

- [x] **Der Cache spart die Geometrie, nicht die Erkennung.** Im selben Lauf
      lief `detect()` **fünfzehnmal** über denselben Körper.

      Die Zahl ist erklärbar und trotzdem ein Befund: `_with_features()` läuft
      in `scene/evaluate.py` nach **jedem** Operationsergebnis — auch nach
      einem Cache-Treffer, wo die Geometrie gar nicht gerechnet wurde. Weg 1
      hat vier Operationen, die ein Objekt ausgeben, und die Auswertung läuft
      beim Öffnen mehrfach (Entwurf; danach noch einmal, wenn die
      Verwaistenprüfung etwas umgeschrieben hat; und in Feinqualität für den
      Prüfbericht). Vier mal drei bis vier ergibt genau die fünfzehn.

      **Dass die Erkennung nach jeder Operation läuft, ist richtig** (§21.2 —
      sonst ist `hole_3` in Schritt fünf ein anderes Loch als in Schritt vier).
      Falsch ist, dass sie auch dann läuft, wenn das Netz nachweislich dasselbe
      ist: Kam das Ergebnis aus dem Cache, ist die Geometrie bitgleich, und
      damit wäre auch das Erkennungsergebnis bitgleich.

      **Der Weg ist nicht offensichtlich**, deshalb steht er hier und nicht in
      einem Commit: Der Plattencache speichert `MeshData` und sonst nichts —
      im selben Protokoll steht dreimal „the disk cache can only store
      MeshData". Die Merkmale bräuchten einen eigenen Platz, und ihre
      Zuordnung hängt außerdem an den *vorigen* Merkmalen und an
      `operation.matches` (§15.7), nicht nur am Netz. Ein Cache, der das
      übersieht, gibt beim zweiten Öffnen andere Namen zurück als beim ersten
      — schlimmer als die Wartezeit.

      Zu messen ist zuerst, **wie viel von den sechs Sekunden überhaupt die
      Erkennung ist**. Ohne diese Zahl ist jeder Umbau hier eine Vermutung.

      **Gemessen und gebaut am 27.08.2026 (`e5816209`).** Über die neun
      Beispielprojekte, je drei Auswertungen wie beim Öffnen: 11,65 s
      Erkennung, davon **7,52 s auf bitgleichen Netzen** — 65 Prozent.
      Gebaut, gemessen: 58,06 s auf 50,20 s, bei „Aushöhlen und teilen" 8,90
      auf 5,33.

      **Das widerspricht der Einschätzung in der Registerzeile, und zwar
      begründet.** Dort stand „hilft dem ersten Öffnen beim Kunden gar
      nicht" — richtig für einen *Platten*cache, der zwischen zwei Sitzungen
      trägt. Die Wiederholungen liegen aber **innerhalb eines
      Öffnungsvorgangs**: Weg 1 wertet dreimal aus, und drei von vier
      `detect`-Aufrufen sehen dabei dasselbe Netz. Ein Cache im Prozess greift
      genau dort, und er greift beim ersten Öffnen so gut wie beim zweiten.

      Der Umbau ist außerdem enger ausgefallen als hier befürchtet: Die
      Zuordnung, die an den vorigen Merkmalen und an `operation.matches`
      hängt, bleibt außen vor — `detect` selbst hängt an nichts als am Netz,
      und nur das liegt im Cache. Was die Zeile über `match()` sagt, gilt
      unverändert und steht als eigener Punkt weiter oben.

- [x] **`decimated 992 to 992 triangles`, dreimal im selben Lauf.** Ein
      Vereinfachungsschritt, der nichts entfernt und trotzdem läuft.

      `decimate()` hat für genau diesen Fall einen frühen Rücksprung
      (`triangle_count <= max(target, DECIMATE_FLOOR)`), und er greift hier
      nicht — die Meldung steht erst *nach* der Vereinfachung. Es läuft also
      eine echte `simplify_quadric_decimation`, die bei 992 Dreiecken anfängt
      und bei 992 aufhört. Entweder liegt das Ziel darunter und das Verfahren
      erreicht es nicht, oder `_welded_for_simplify` gibt etwas anderes zurück,
      als der Aufrufer erwartet.

      **Geklärt und behoben am 27.08.2026 (`f06b4c40`) — beide Vermutungen
      waren falsch.** Das Netz ist sauber verschweißt (1488 Nachbarschaften
      bei 992 Dreiecken, also genau drei Halbe je Dreieck), wasserdicht, eine
      Komponente, keine entarteten Dreiecke. `simplify_quadric_decimation`
      erreicht kein einziges Ziel von 900 bis 400, auch direkt gerufen und
      ohne Zusatzdaten; dieselbe Rechnung trifft an Kugel und Quader jedes
      Ziel exakt. Die Euler-Zahl sagt warum: minus acht, also Genus fünf — ein
      CAD-Teil mit fünf Durchbrüchen, das bereits minimal trianguliert ist.
      Jede Kante trennt zwei Ebenen, und eine solche zusammenzuziehen hieße,
      die Form zu ändern.

      Die Vereinfachung verhält sich damit **richtig**; falsch war, dass sie
      schweigt. Der Kunde las „Die Fläche hat sich dabei kaum verschoben" —
      zutreffend und vollkommen nebensächlich. Jetzt sagt sie es
      (`mesh.not_simplified`), als Auskunft und nicht als Warnung, und nur wo
      gar nichts geschah.

---

## Die Krümmungskarte lag an Kugeln zehn Prozent daneben (23.08.2026)

Gefunden beim Abarbeiten des Punktes „Ein Test, der nur seine eigene Konsistenz
misst" — und zwar auf genau dem Weg, den dieser Punkt vorschreibt: **gegen
einen Sollwert prüfen, nicht gegen die eigene Wiederholbarkeit.**

- [x] **Der Zylinder konvergiert, die Kugel nicht.** Gemessen gegen den Radius
      selbst, über vier Netzfeinheiten:

          Zylinder r=10,  96 -> 768 Dreiecke:    0,989 -> 1,000   konvergiert
          Kugel    r=10, 320 -> 20480 Dreiecke:  0,887 -> 0,904   konvergiert nicht

      Bei 64-facher Verfeinerung bleibt der Fehler stehen. **Ein Test, der zwei
      Vernetzungen gegeneinander hält, wäre grün geblieben** — dasselbe Muster
      wie beim Zwei-Drittel-Fehler, den dieselbe Karte einmal hatte.

- [x] **Zwei naheliegende Erklärungen sind gemessen und widerlegt**, beide von
      ihren eigenen Urhebern. Das ist der lehrreichste Teil:

      *„Das Minimum greift den Ausreißer, der Median hilft."* (64) — falsch.
      Beim Torus trifft der Median die Ringkrümmung statt der Röhre und liegt
      um das Dreieinhalbfache daneben. 3a hat es mit größerem Abstand
      bestätigt (+100,8 %) und zusätzlich p5, p10 und p20 durchprobiert: **Es
      gibt keine Ordnungsstatistik, die alle drei Körper bedient.**

      *„Der Testkörper ist eine UV-Kugel, ihre Pole sind entartet."* (3a) —
      genau verkehrt herum. Die UV-Kugel ist die, die sich **richtig** verhält
      (-1,1 % → -0,1 %, konvergiert); die Icosphere ist die, die nicht
      konvergiert.

- [x] **Die Ursache ist ein Formfaktor der Vernetzung** (3a). Eine Icosphere
      ist selbstähnlich: Nach jeder Unterteilung sind die Dreiecke an den zwölf
      Ikosaeder-Ecken anders geformt als in der Flächenmitte, und das Muster
      wiederholt sich in jeder Auflösung. Über alle Nachbarschaften ist der
      **Mittelwert** richtig, die Verteilung nur schief — das Minimum greift
      die schrägste.

      **Warum es Zylinder und Torus nicht trifft:** Beide haben eine
      ausgezeichnete Hauptkrümmungsrichtung, und ihre Vernetzung folgt ihr —
      es gibt Nachbarschaften, die quer liegen und exakt `r` liefern. Auf einer
      Kugel liegt **keine** in einer Hauptkrümmungsebene.

- [x] **Es trifft echte Modelle, und genau eine Merkmalsart.** Die Messung, die
      darüber entschied, ob es ein Testkörper-Artefakt ist — Karte gegen
      Erkennung, auf den Dreiecken des Merkmals:

          sphere_socket.stl    sphere   Erkennung 7,969   Karte 7,211   -9,5 %
          post_with_fillet     pin      Erkennung 6,000   Karte 5,996   -0,1 %
                               torus    Erkennung 2,994   Karte 2,992   -0,1 %
          block_with_rounded   fillet   Erkennung 2,999   Karte 2,998   -0,0 %
          torus_ring           torus    Erkennung 4,957   Karte 4,937   -0,4 %

      Vier von fünf unter einem halben Prozent, eine bei -9,5 %.

- [x] **Behoben in `7e2de9c`** (3a): Die Karte nimmt den **gemessenen** Radius,
      wo ein Merkmal einen liefert, und schätzt nur dort, wo keines ist. Der
      Grund steht im Docstring: `fit_sphere` rechnet einen Ausgleich über alle
      Punkte, die Karte schätzt aus **einer** Nachbarschaft — und eine einzelne
      kann schräg liegen, eine Ausgleichsfläche nicht.

      Die Herkunft weist die Legende in Worten aus (§22.5, Regel 18): „Wo ein
      Merkmal erkannt wurde, steht sein gemessenes Maß — sonst eine Schätzung
      aus den Nachbarflächen." Nachgemessen am selben Messpunkt: -9,5 % → +0,0 %.

      **Der Kegel bleibt bewusst draußen** — sein Radius ändert sich über die
      Höhe, ein einzelner Wert wäre dort für fast jedes Dreieck der falsche.

- [x] **Der Torus-Eintrag griff ins Leere, und niemandem fiel es auf.**
      `_FEATURE_RADIUS` sucht `"minor_radius"`; das Merkmal trägt
      `tube_diameter`. Gemessen an `torus_ring.stl`: der Schlüssel existiert
      nicht, der Eintrag läuft ins `continue`.

      **Warum es stumm blieb, ist der eigentliche Punkt:** Die Schätzung trifft
      den Torus ohnehin auf 0,4 %, weil er eine ausgezeichnete
      Hauptkrümmungsrichtung hat. **Ein Tabelleneintrag, der nichts bewirkt,
      sieht dort genauso aus wie einer, der wirkt** — vier Tests bleiben grün,
      und die Zahl daneben stimmt.

      **Behoben in `9afcbbd`** (3a): `("tube_diameter", 0.5)` statt
      `("minor_radius", 1.0)` — falsch waren der Name **und** der Faktor.
      Nachgemessen über den ganzen Korpus: alle fünf Einträge greifen,
      `torus_ring` und `post_with_fillet` auf +0,0 %.

      **Wie der Eintrag entstand, ist der eigentliche Ertrag** (3a hat es
      selbst aufgeschrieben): Vier der fünf Einträge sind an vierzehn
      Korpusdateien **gemessen**; in diesen vierzehn war kein Torus, und statt
      die Messung zu erweitern, wurde der fünfte Name aus dem Kopf ergänzt.

      > **Eine Tabelle, deren Einträge vier gemessen und einer geraten sind,
      > sieht beim Lesen homogen aus.**

      Das ist dieselbe Tarnung wie beim falschen Kommentar in
      `finish_body_drag` am selben Tag: Eine Vermutung, die neben belegten
      Aussagen steht, erbt deren Glaubwürdigkeit.

      Der Test prüft deshalb **die Verbindung und nicht das Ergebnis** — trägt
      das Merkmal den Parameter, den die Tabelle sucht? Gegengeprobt an zwei
      erfundenen Schlüsseln, beide rot. Und er zählt, wie viele Einträge er am
      Korpus überhaupt erreicht hat: unter vier schlägt er fehl, sonst prüfte
      er bei einem geänderten Korpus wieder seine eigene leere Menge.

---

## Was erst am Verkaufsstart fällig wird (24.08.2026)

Gemeldet von `3d-druck-bd` aus der Auslieferung von 0.1.4 und der
Rechtstext-Durchsicht (`3d-druck-58`): vier Textarbeiten, die heute niemand
machen kann, weil sie an Gewerbeanmeldung, Rechtsprüfung und Verkaufsstart
hängen. **Genau solche Punkte fallen durch** — an dem Tag, an dem sie dran
sind, fallen sie niemandem ein.

Sie stehen hier und nicht am Ende von `konzepte/konzept-demo-2026-10.md`,
obwohl das Konzept die Bedingungen für 1.0 schon führt: `CLAUDE.md` sagt,
offene Arbeit steht im Register und nirgends sonst, und der Grund dafür ist
genau der Fall, der sich beim Nachprüfen dieser vier Punkte wiederholt hat.

**Einer der vier hält der Prüfung am Code nicht stand**, und bei einem zweiten
habe ich das Gegenteil dessen gemessen, was gefragt war (siehe unten):

- **„Kaufknopf fehlt" ist keine Lücke, sondern Absicht.**
  `konzept-demo-2026-10.md` §H: „Kein Verkauf während der Demo. Das entlastet
  die Rechtsseite erheblich: ohne entgeltlichen Vertrag greift die
  Widerrufsbelehrung nicht." Der Knopf ist Arbeit **zum Start**, nicht ein
  Mangel von heute.

Bleiben drei, und alle drei sind echt:

- [x] **Der Zahlungsanbieter steht namentlich da, ohne dass ein Vertrag
      besteht.** `datenschutz.html` nennt ihn mit voller Anschrift — „Paddle.com
      Market Limited, 30 Old Bailey, London EC4M 7AU" — und führt ihn als
      Empfänger personenbezogener Daten samt Drittlandsbegründung nach Art. 45
      DSGVO. Ein Konto gibt es nicht; ohne Gewerbeanmeldung kann es keines
      geben.

      **Zwei Antworten sind vertretbar, und es ist keine technische Frage:**
      Der Name bleibt (dann stimmt der Text am Starttag) oder er wird bis
      dahin durch „der Zahlungsdienstleister" ersetzt (dann stimmt er heute).
      **Robert vorgelegt am 23.08.2026** durch `3d-druck-bd`.

      Den zeitlichen Vorbehalt hat `3d-druck-58` inzwischen eingebaut
      (`5950321`): Die Datenschutzerklärung sagte im Präsens „Der Kauf läuft
      nicht über diese Website, sondern über … Paddle", jetzt heißt es „läuft
      **dann** nicht" — derselbe Vorbehalt, den die AGB schon trugen. Die
      Namensfrage bleibt davon unberührt.

      **Und hier steht, wie ich diesen Punkt fast abgeräumt hätte**, weil der
      Fehler die vierte Ausprägung derselben Sache an einem Abend ist: Ich habe
      gemessen, ob Paddle in den Texten steht — fünfmal, ja —, und daraus
      „erledigt" geschlossen. **Die Messung war richtig und beantwortete die
      falsche Frage.** Gefragt war nicht „steht der Anbieter drin?", sondern
      „soll er drinstehen, bevor es ihn gibt?". Das ist wörtlich die Gegenfrage
      aus `.claude/rules/tests.md`: *Was habe ich gerade gemessen, und ist das
      dasselbe wie das, was ich wissen wollte?* — diesmal nicht an einem

      **Erledigt, festgestellt am 26.08.2026:** In `website/` steht kein
      „Paddle" mehr — die Datenschutzerklärung sagt „Zahlungsdienstleister.
      Welcher das ist, steht vor dem Kauf …", also die heute-wahre Variante,
      die Robert am 25.08. mit „alles perfekt für Kunden machen" gedeckt hat.
      Der Punkt stand länger offen als sein Fix; die Namenszeile kehrt am
      Starttag mit dem echten Vertrag zurück.
      Werkzeug, sondern an einer Meldung.


- [ ] **Der Entwurfsvermerk muss von den Rechtstexten herunter**, sobald die
      fachliche Prüfung durch ist. `agb.html`, `eula.html` und
      `widerruf.html` tragen je einmal „Sorgfältiger Entwurf, aber keine
      Rechtsberatung"; erzeugt wird er in `tools/make_legal.py:236`. Also eine
      Zeile im Werkzeug und ein Neuerzeugen — **nicht** drei Stellen von Hand,
      die beim nächsten Lauf wiederkämen.

- [ ] **Impressum ohne USt-IdNr. oder Steuernummer.** `website/impressum.html`
      nennt heute Name, Anschrift und E-Mail; gemessen: keine der beiden
      Angaben steht darin. Kommt mit der Gewerbeanmeldung und ist bis dahin
      nicht nachholbar — §5 TMG verlangt sie, sobald es sie gibt.

## Ein Tor, das nicht durchfiel und trotzdem die halbe Prüfung ausließ (24.08.2026)

Nach dem Pull von 761 Commits auf `494439a3` einmal das volle Tor gefahren.
Es meldete „Läufe mit Fehler: 3": zwei bekannte sporadische Fensterabstürze
(`test_pose_session`, `test_sculpt_session` — siehe oben, beide je zweimal
nachgefahren und grün) und dazwischen `rest-in-einem-zug(Exit:4)`.

Der dritte war kein Fehlschlag, sondern ein **Nichtlauf**. Die Sammelgruppe in
`suite-getrennt.sh:182` fährt alles ohne Qt in einem Zug und ruft dafür
`pytest … -n "$KERNE"`; `pytest-xdist` stand aber weder in `pyproject.toml`
noch in `constraints.txt`. Ohne das Paket antwortet pytest mit
`unrecognized arguments: -n` und Exit 4, und die 3554 Tests ohne Qt —
Geometrie, Skizzen, Schichtanalyse, Agentenschicht — liefen nicht.

**Ein Tor, das nicht durchfällt, sondern die halbe Prüfung stillschweigend
auslässt, ist schlimmer als eines, das rot ist.** Es sah aus wie drei rote
Dateien und war „der Großteil fehlt".

`tools/check_env.py` konnte es nicht melden: Es vergleicht das Installierte
gegen `constraints.txt` und sieht damit nur, was jemand aufgeschrieben hat.
Eine Voraussetzung, die nirgends steht, hat es für dieses Werkzeug nie
gegeben. Dass ausgerechnet die Datei, die den Fassungssatz hütet, die Lücke
nicht sehen kann, ist kein Mangel des Werkzeugs, sondern die Grenze seiner
Frage.

- [x] **`pytest-xdist` deklariert** (`ad2d1729`): `>=3.6` in der dev-Gruppe,
      festgeschrieben auf 3.8.0, dazu execnet 2.1.2. Beide MIT und reine
      Testabhängigkeit — `licences.toml` führt kein dev-Werkzeug (kein pytest,
      ruff, mypy, forked) und `RUNTIME_EXTRAS` kennt nur geom, ui, agent und
      brep, also bleiben Lizenzprüfung und `THIRD-PARTY-NOTICES.md` zu Recht
      unberührt. Nachgewiesen am selben Stand: „Läufe mit Fehler: 0", 3554
      passed und 23 skipped in 61 s. Dieselben Tests seriell: 267 s — das ist
      der Grund, warum das Skript `-n` überhaupt will.

- [x] **Ein Nichtlauf zählt wie ein Fehllauf.** `zaehlt_als_fehler`
      (`suite-getrennt.sh:145`) erhöht `fails` um eins, gleich ob eine
      Fensterdatei mit drei roten Tests endet oder die Sammelgruppe mit 3554
      Tests gar nicht erst anläuft. Der Schlussbericht nennt nur eine Zahl,
      und die Zahl trägt ihr Gewicht nicht mit — dieselbe Sache wie „Eine Zahl
      trägt ihre Bedeutung nicht mit" weiter oben, diesmal im Tor selbst.
      Zu überlegen: den Ausfall der Sammelgruppe gesondert melden, weil er die
      Aussagekraft des ganzen Laufs aufhebt, statt sie um ein Drittel zu
      mindern.

- [x] **Exit 5 wäre derselbe Fall und käme als grün durch.** Zeile 149 wertet
      „keine Tests gesammelt" pauschal als keinen Fehler. Für eine einzelne
      Fensterdatei ist das richtig; für die Sammelgruppe hieße es, dass 3554
      Tests nicht gesammelt wurden, und das Tor meldete „Läufe mit Fehler: 0".
      Gemessen ist dieser Fall nicht — er steht hier, weil der heutige zeigt,
      dass die Zählung nicht zwischen „nichts gefunden" und „nichts gelaufen"
      unterscheidet.

**Beide behoben in `3916cb1f`, und zwar anders als hier vorgeschlagen** (von
formwerk-20 am 24.08.2026 am Code nachgeprüft und nachgetragen, weil die
schreibende Sitzung nicht mehr erreichbar war). Nicht die *Zählung* wurde
geändert, sondern der *Bericht*: `zaehlt_als_fehler` erhöht `fails` weiterhin
nur um eins, und `[ "$status" -eq 5 ] && return 1` steht unverändert in Zeile
174. Dafür schreibt das Skript jetzt die Zusammenfassungszeile der
Sammelgruppe eigens hin (`Sammelgruppe: 3554 passed, 23 skipped in 58.61s`),
und fehlt sie, stehen drei `!!`-Zeilen da: „kein einziger Test ohne Qt wurde
ausgeführt … sagt nichts über den Code."

Das löst beide Punkte, weil bei Exit 5 keine „N passed"-Zeile entsteht — der
Fall ist also sichtbar, ohne dass die Zahl ihn zählt. Und es ist der bessere
Weg: Eine Zahl, die Nichtlauf und Fehllauf verschieden gewichtet, müsste
gewichten *können*; eine Zeile, die den Umfang des Laufs nennt, muss nur
dastehen. Wer sie einmal gelesen hat, sieht beim nächsten Mal, wenn statt 3554
plötzlich 120 dort steht — und das ist bei Aufräumarbeit der wahrscheinlichere
Schaden als ein roter Test.

## Fünf Doppelungen, und eine hatte schon Folgen (24.08.2026)

Ein Durchgang durch `app/core` mit der Frage, was aufzuräumen ist — 159 Dateien,
60 870 Zeilen. Das Ergebnis vorweg, weil es das eigentliche ist: **Fast nichts.**
Kein toter Code (die fünf Kandidaten, die eine Textsuche findet, sind alle über
`@register_op` oder `@register_part` registriert und damit nur textuell
unsichtbar). Keine Kante aus dem Kern in die Oberfläche. Keine Funktion über
McCabe-Komplexität 12. Kein einziges `TODO`, `FIXME`, `HACK` oder `XXX` in `app/`
und `tools/`. Keine überflüssige `type: ignore` — `strict = true` schaltet
`warn_unused_ignores` ein, und mypy ist grün, also gibt es sie nicht.

Die vier Import-Kreise, die eine Graphanalyse meldet, sind alle zur Laufzeit
gebrochen oder mit Begründung offen: `geom.mesh ↔ export.threemf` läuft über
`TYPE_CHECKING` und einen Funktionsimport, beide mit Kommentar daneben;
`activation` und `knowledge.parts` stehen als bekannte Fälle in
`test_core_isolation.py`. **Die erste Messung war hier falsch** und hätte einen
Fund gemeldet, den es nicht gibt: Ein Skript, das `TYPE_CHECKING`-Importe wie
echte zählt, sieht Kreise, die zur Laufzeit keine sind. Wer Architektur
vermisst, muss den Unterschied kennen.

Geblieben sind fünf Doppelungen. Vier davon hätten irgendwann geschadet, eine
hatte schon geschadet.

- [x] **Dieselbe Rotationsmatrix in zwei Modulen** (`8d828a12`).
      `_rotation_to_down` lag byte-identisch in `geom/orient.py` und
      `slice/orientation.py`, siebzehn Zeilen, einmal mit Docstring und einmal
      ohne. Der Import war die ganze Zeit offen — `slice/orientation.py` holt
      `candidates` seit je aus demselben Modul. Jetzt öffentlich als
      `rotation_to_down`. 93 Tests.

- [x] **Fünf von sechs Nullprüfungen sagten nicht, was sie prüften**
      (`ee75d0d7`). „Dieses Maß muss größer als null sein." stand sechsmal in
      vier Dateien; die private Hilfe in `sketch/shapes.py` setzte
      `constraint="positive"`, die fünf ausgeschriebenen nicht. Jetzt
      `require_positive` in `errors.py`, sechzehn Aufrufstellen, der Satz
      einmal. **Das ist die Doppelung, die schon geschadet hatte:** Zwei der
      fünf prüften mehrere Maße in *einer* Bedingung und nannten dann immer das
      erste — wer bei einem Gitter `wall` auf null setzte, bekam `cell`
      markiert und suchte am falschen Eingabefeld. 342 Tests.

- [x] **Zwei Parametertexte, zwanzigmal geschrieben** (`b7f73b2d`). „Wie das
      Objekt im Baum heißt…" zehnmal, „Null heißt: Wert aus dem kalibrierten
      Materialprofil." elfmal. Jetzt `NAME_DOC` und `AUTO_FROM_PROFILE_DOC` in
      `registry/params.py`. Dass zwanzig Kopien auseinanderlaufen, stand schon
      im Bestand: `ingest/ops.py` sagt „Leer **übernimmt den Dateinamen**", und
      das ist dort richtig und bleibt eigen.

- [x] **Eine Regel für Zollstellen, zweimal aufgeschrieben** (`453cfa98`).
      `format_volume` und `format_area` trugen dieselbe Schleife;
      `_significant_decimals` in `units.py`. 162 Tests.

- [x] **Dieselbe Profilauswahl für Prozesse und Filamente** (`d959274b`). Acht
      Zeilen, Unterschied eine Zeichenkette. Der Rückfall auf Profile ohne
      Verträglichkeitsliste war nur bei den Prozessen begründet — bei den
      Filamenten traf derselbe Code dieselbe Entscheidung ohne einen Satz dazu.
      Beide öffentlichen Namen bleiben, `_of_kind` darunter. 285 Tests.

**Der Nachweis, der zählt:** Ein Skript liest alle 86 Operationen, 18 Bausteine
und 547 Parameter samt aufgelöster Titel, doc-Texte, Grenzen, Einheiten,
Vorgaben und Kürzel. Gegen einen zweiten Arbeitsbaum auf dem Stand davor
gehalten: **Zeichen für Zeichen identisch.** Bei einer Aufräumarbeit ist das die
richtige Frage — nicht „ist ein Test rot", sondern „sieht der Kunde etwas
anderes". Dazu die Sammelgruppe unverändert bei 3554 passed / 23 skipped vor
und nach dem Umbau, und genau darauf ist zu sehen: Tests zu *verlieren*, ohne
dass einer rot wird, ist hier der wahrscheinlichere Schaden.

**Diese Zahl ist eine Messung mit Datum, kein Sollwert** — sie wächst mit jedem
neuen Test. Am 24.08.2026 gegen Mittag stand sie bei 3554, wenige Stunden später
bei **3559**, und die fünf zusätzlichen waren die Skizzentests einer parallel
laufenden Sitzung. Wer sie als feste Grenze liest, sucht eine Regression, wo
jemand nur Tests geschrieben hat. Brauchbar ist sie **innerhalb eines
Arbeitsschritts**: vorher messen, nachher messen, und die Differenz muss man
erklären können. Genau so ist sie hier verwendet.

Was offen bleibt:

- [x] **Zwei Kernfunktionen sind in der Oberfläche nachgebaut.**
      `app/ui/sketch_editor.py:373` `flat_offsets` ist wortgleich
      `edit.offsets_of`, `:383` `_flat_points` wortgleich `edit.flat_points` —
      und `from app.core.sketch import edit` steht in Zeile 48 schon da. Elf
      Aufrufstellen, rein mechanisch; `Point2` ist `tuple[float, float]`, die
      Rückgabetypen sind identisch. Nicht angefasst, weil die Datei einer
      anderen Sitzung gehörte; `formwerk-9e` nimmt es in das Paket mit, das die
      Koordinatenrechnung des Canvas anfasst.

- [x] **Gehört „positive" in `_RANGE_CONSTRAINTS`?** Eine fachliche
      Entscheidung über einen Oberflächentext, keine Aufräumarbeit.
      `ValidationError` setzt den Titel „Ein Wert liegt außerhalb des
      zulässigen Bereichs." nur für `minimum`, `maximum` und `range`; sonst
      gilt „Die Eingabe war so nicht verwendbar." Für „Dieses Maß muss größer
      als null sein" wäre der erste Satz der passendere — es *ist* eine
      Bereichsverletzung. Betrifft alle sechzehn Aufrufstellen von
      `require_positive` und ändert, was der Nutzer als Überschrift liest;
      deshalb hier und nicht im Commit von heute.

- [ ] **43 Texte stehen mehrfach wortgleich im Quelltext, quer über Dateien.**
      Neu gemessen am 27.08.2026 über einen AST-Lauf durch `app/`, der die
      Argumente von `_()` und `tr()` ab 25 Zeichen sammelt: 1997 Texte
      insgesamt, 94 davon mehr als einmal. **Die Aufteilung ist der eigentliche
      Befund**, nicht die Summe: 50 stehen mehrfach in *derselben* Datei — das
      sind Zweige derselben Funktion, wer den einen ändert, sieht den anderen.
      44 standen quer über Dateien, und nur die laufen auseinander, weil
      niemand die andere Stelle sieht. Einer davon ist zusammengelegt (siehe
      unten), bleiben 43.

      Die beiden Fälle, die dieser Punkt bis heute namentlich nannte, sind
      längst behoben: „Bitte zuerst ein Objekt auswählen." und „Dafür braucht
      es einen Körper in der Szene." stehen je **einmal** in
      `app/ui/main_window.py` (Zeilen 268/269). Der Punkt führte sie noch als
      viermal — und trug seine eigene Zahl in drei Fassungen: 81 im Register,
      85 in der Überschrift, 87 im Fließtext.

      **Zusammengelegt (ca9a5e33):** „Dabei ist etwas schiefgegangen, womit hier
      niemand gerechnet hat." — der Satz, den vier Dialoge sagen, wenn ein
      Arbeiter im Hintergrund abstürzt (ComfyUI einrichten, Modell prüfen,
      Erzeugen, Installieren). Er steht jetzt als `UNEXPECTED_CRASH` in
      `app/ui/labels.py`, dem Modul, dessen Docstring genau das verspricht:
      kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

      **Was die 43 wirklich kosten, und warum sie nicht oben stehen:** Läuft
      eine der Stellen auseinander, entstehen zwei Katalogschlüssel, und der
      neue ist unübersetzt — das meldet `tests/test_translations.py` beim
      nächsten Lauf. Der Kunde sieht also keinen falschen Text, sondern
      höchstens einen deutschen in einer fremden Sprache, und das Tor hält es
      auf. Es ist Wartungsaufwand, kein Kundenschaden. Wer in einer der Dateien
      ohnehin arbeitet, nimmt seinen Fall mit; ein eigener Durchgang über alle
      43 lohnt nicht. Das Messskript steht in der Sitzung vom 27.08.2026 und
      ist in zwanzig Zeilen wieder gebaut: `ast.walk` über `app/`, Aufrufe von
      `_`/`tr` mit reinem Zeichenkettenargument, nach Text gruppieren, die mit
      mehr als einer Datei behalten.

---

## Ein Knopf, der einen Schritt legte und nichts bewegte (24.08.2026)

Robert hat es gemeldet, während die Anwendung lief: „das an druckbett ausrichten
funktioniert nicht mehr" — Dialog kommt, OK gedrückt, danach passiert nichts.

Der Menüeintrag war es nicht. Über *Auf dem Bett anordnen* im Menü wandern zwei
Würfel von (-10,-10,-10) auf (-105, 85, 0) und (-80, 85, 0), und im echten
Fenster mit VTK wandern die Aktoren mit. Es war der **Knopf gleichen Namens,
den ein Befund anbietet** — `arrange.off_the_plate` im Prüfbericht, derselbe
Knopf auch im Fehlerdialog der Slicer-Übergabe.

`_arrange_after_error` trug die Operation **ohne Eingaben** in den Stapel, mit
der Begründung, sie arbeite ja über die ganze Szene. Das ist der Unterschied,
an dem es hing: „über die ganze Szene" heißt nicht „ohne Eingaben". Der Stapel
plant die Ausgänge eines Schritts, und für eine Operation mit variabler
Objektzahl ohne Eingaben sind das keine (`History._outputs_for`) — der
Kommentar dort behauptete sogar ausdrücklich, das Fenster reiche die Szene
immer über `inputs_for` herein, und genau diese eine Stelle tat es nicht.

Gemessen: Der Schritt landet im Verlauf mit `inputs=()` und `outputs=()`, die
Auswertung meldet `complete=True` und `stopped_at=None`, kein Körper bewegt
sich, und der Befund, gegen den der Knopf angeboten wurde, steht danach
unverändert im Bericht. Kein Fehler, keine Meldung, nichts.

Getroffen hat es den häufigsten Importfall überhaupt — eine 3MF aus Bambu
Studio, Orca oder Elegoo führt Bettkoordinaten, ihre Körper liegen neben dem
Bett, und `.claude/rules/oberflaeche.md` nennt genau diesen Knopf als die
Handlung, die dort hilft.

- [x] **Der Knopf wirkt** (`a22ffa48`): Die Eingaben kommen über `inputs_for`,
      aus demselben Grund, aus dem Menü, Palette und Fernaufruf sie dort holen.
      Der Abstand kommt aus der Druckbetthaftung wie im Dialog des
      Menüeintrags — hier ist er nicht Vorbelegung, sondern die einzige
      Gelegenheit: Ein Knopf ohne Dialog fragt nichts, und zwei Teile mit je
      fünf Millimetern Brim stehen einander sonst auf der Platte im Weg. Der
      Test drückt den echten Knopf unter der Befundliste, nicht den Handler von
      Hand; Gegenprobe gefahren, ohne den Fix rot mit „der Knopf hat nichts
      bewegt".

- [ ] **Offscreen prüft nichts, was am Aktor hängt.** `Viewport.show_scene`
      kehrt bei `self.plotter is None` zurück, bevor ein einziger Aktor gebaut
      wird (`app/ui/viewport.py:1948`), und die ganze Suite läuft offscreen.
      Die erste Probe verglich `_actors` vor und nach der Operation und
      verglich damit zwei leere Dicts — grün ohne Aussage. Das ist dieselbe
      Bauform wie „Ein Verbotstest über eine leere Menge ist immer grün"
      (`.claude/rules/tests.md`), nur eine Ebene weiter: Nicht der Filter ist
      leer, sondern die Welt, über die er filtert. Betroffen ist jede Zusage
      über Aktoren, Farben, Kamerastellung und Bildinhalt — und damit ein
      Gebiet, in dem gerade zwei Sitzungen arbeiten. Nachstellen ließ es sich
      nur mit echter Event-Loop und sichtbarem Fenster, die Schritte an einer
      `QTimer.singleShot`-Kette statt in einer Warteschleife; `wait_for_idle`
      hängt dort.

      **Nachtrag vom 24.08.2026 aus „Ein Klick in eine Bohrung traf die Fläche,
      oder gar nichts": Es ist nicht nur der Aktor, es ist der ganze
      Klickpfad.** `vtkCellPicker` antwortet offscreen ebenso wenig, und damit
      ist alles ungeprüft, was von einer Bildschirmstelle ausgeht — sieben
      Tests in `tests/test_selection.py` fütterten `_feature_at` mit Punkten,
      die ein echter Picker an dieser Stelle **nie** zurückgibt. Die Rechnung
      war korrekt, die Eingabe gab es nicht; ein Klick mitten in eine
      Durchgangsbohrung hob in der Draufsicht die Auswahl auf, und kein Test
      konnte das sehen.

      **Das Verfahren, mit dem es messbar wurde**, und es kostet zwanzig
      Zeilen im Scratchpad: `QT_QPA_PLATFORM` aus der Umgebung nehmen
      (`os.environ.pop`), Fenster `show()`, `processEvents()`, `show_scene`,
      Kamera über `plotter.view_xy()` stellen und rendern. Den Weltpunkt, auf
      den geklickt werden soll, rechnet der Renderer selbst in Pixel um
      (`SetWorldPoint` → `WorldToDisplay` → `GetDisplayPoint`) — damit ist der
      Klick reproduzierbar auf einer bekannten Stelle der Geometrie und nicht
      auf einer geratenen Bildkoordinate. Gepickt wird dann über den
      Produktionsweg (`viewport._world_at(x, y)`), nicht über einen eigenen
      Picker: Sonst prüft der Prüfstand seine eigene Nachbildung. Für die
      Gegenprobe eignet sich jede Ansicht, die dieselbe Stelle anders trifft;
      `view_xz` liefert hier den Fall „Merkmal liegt hinter dem Material".

- [ ] **Ein Prüfstand, der beim Fehlschlag modal stehen bleibt.** Derselbe
      Prüfstand ohne `app.core.bootstrap.load_operations()` endet beim ersten
      Import in `unknown operation 'load'` — und der Fehler öffnet
      `report_error`, also einen **modalen** Dialog. Der Hauptthread stand, die
      Timer feuerten nicht mehr, und von außen war es von einem Hänger nicht zu
      unterscheiden: zwei Läufe über je drei Minuten ohne eine Zeile Ausgabe.
      Gesagt hat es erst der Ordner, den die Anwendung dabei still anlegt
      (`%LOCALAPPDATA%\RS Digital\Solidon3D\reports\`) — dort stand der
      Traceback. Ein Werkzeug, das beim Fehlschlag stehen bleibt statt zu sagen,
      was los ist, kostet jeden Nachfolger dieselbe Stunde.

**Und eine Lehre für den geteilten Baum, die keinen eigenen Punkt braucht:**
Eine Gegenprobe ist für jede andere Sitzung ein roter Test. Der Test hier war
etwa eine Minute lang rot, weil der Fix für den Nachweis per `git stash`
beiseite lag — genau in dieser Minute fuhr eine fremde Sitzung ihr Tor und
meldete ihn. Wer stasht, sagt es vorher an oder tut es im eigenen Arbeitsbaum.

---

## Ein Klick in eine Bohrung wählte die Fläche, oder nichts (24.08.2026)

Roberts Meldung: „wenn wir eine bohrung anklicken erwischen wir oft nur die
oberfläche und kommen nicht zur Bohrung". Am 23.08. war an derselben Stelle
schon einmal gearbeitet worden — die Reichweite eines Merkmals und „mitten im
Loch ist kein Dreieck" stammen von dort. Beides war richtig und beides griff
nicht, weil der Fehler **vor** dieser Rechnung lag.

Gemessen am echten `vtkCellPicker` in einem **sichtbaren** Fenster (offscreen
antwortet er nicht), Korpusplatte, Bohrung 32 Bildpunkte breit, Pixel neben der
Bohrungsmitte:

| | Draufsicht | Isometrisch | Vorderansicht |
|---|---|---|---|
| 0–8 px | **kein Treffer** → `hole_1` | `hole_1` → `hole_1` | `face_3` → `face_3` |
| 12 px | `hole_1` → `hole_1` | **kein Treffer** → `hole_1` | `face_3` → `face_3` |
| 16 px | **`face_2`** → `hole_1` | **`face_2`** → `hole_1` | `face_3` → `face_3` |
| 24 px | `face_2` → `face_2` | `face_2` → `face_2` | `face_3` → `face_3` |

- [x] **Senkrecht in eine Durchgangsbohrung traf der Strahl kein Dreieck.** Die
      Zylinderwand liegt parallel zu ihm, dahinter kommt keine Fläche; der
      Picker gab über der **ganzen** Bohrung nichts zurück.
      `Viewport._on_left_click` machte daraus `objectPicked.emit("")` — ein
      Klick mitten in die Bohrung **hob die Auswahl auf**, und zwar ausgerechnet
      in der Ansicht, in der man ein Lochbild anklickt. `_feature_inside`
      („mitten im Loch ist kein Dreieck", 23.08.) konnte das nicht fangen: Es
      braucht einen Punkt, und es gab keinen.
- [x] **Landete der Strahl daneben auf der Deckfläche, gewann sie immer.** Ihr
      Abstand ist null, der der Bohrung größer als null — `FEATURE_REACH_SHARE`
      ist eine Obergrenze und kein Vorrang, und damit war die Konstante für
      Bohrungen wirkungslos. Gemessen gab ein Punkt 0,4 mm neben dem
      Bohrungsrand `face_2`, bei einer Reichweite von 0,95 mm.
- [x] **Gefragt wird jetzt der Sichtstrahl** (`_pick_ray` → `_bore_aim`,
      gerechnet in der freien Funktion `bore_span`): Welche Bohrung durchquert
      er, **bevor** er auf dem Sichtbaren landet? Die Grenze `until` ist das
      Stück, ohne das es falsch wird — hinter der Stirnfläche liegt jede Bohrung
      der Platte, und die dritte Spalte oben bleibt deshalb unverändert
      `face_3`. Zurück kommt ein Punkt **auf der Bohrungsachse**, nicht der
      Auftreffpunkt: Damit bleibt die Kette dahinter unberührt — Stufung,
      Kontextmenü und Zeiger bekommen einen Punkt wie immer.
- [x] **Auch die gesenkte Durchgangsbohrung, die häufigste eines Druckteils.**
      Gemessen an `plate_countersunk.stl` durch den Einleseweg der Anwendung:
      vorher `None`, jetzt `hole_1` — die Bohrung und nicht die Senkung
      (`cone_1`), wie „die engste gewinnt" es in `_feature_inside` schon sagte.
      Das gesenkte Sackloch war vorher schon erreichbar (der Boden liefert einen
      Treffer) und bleibt es.
- [x] **Der Vorrang gilt der Auswahl, nicht jedem Klick.** Formen, Bemalen,
      Messen, Trennen und Skelett setzen eine **Stelle** auf der Oberfläche; ein
      Punkt auf der Achse wäre dort einer in der Luft. Die Weiche liest die
      Rangfolge aus `_resting_role` statt die fünf Flaggen ein zweites Mal
      aufzuzählen — laufen die zwei Listen auseinander, setzt ein Pinselstrich
      seine Farbe dort, wo der Zeiger eine Bohrung versprach.
- [x] **Der Zeiger fragt dasselbe wie der Klick**, jetzt über einen Zell-Pick je
      Ruhepause statt über den Tiefenpuffer. Gemessen 0,16 ms; die Zusage ist es
      wert, denn eine Bohrungsform am Zeiger, die der Klick nicht einlöst,
      verspricht etwas, das nicht eintritt.

**Ein Messfehler auf dem Weg, und er gehört hierher, weil er zwei Minuten von
einem Fehlalarm entfernt war:** Der erste Aufbau lud die Korpusdateien mit
`trimesh.load` statt über `read_mesh` + `normalise`. In `plate_countersunk.stl`
erkannte `detect` damit **keine** Bohrung, nur sechs Flächen — was wie ein
schwerer Erkennungsfehler aussah und keiner war: Die Anwendung führt Vertices
beim Einlesen zusammen, und die Zylindersuche hängt an dieser Nachbarschaft. Bei
`plate_holes.stl` fiel es nicht auf, dort fand sie die vier Bohrungen auch ohne.
Ein Prüfaufbau, der den Weg der Anwendung nachbaut, muss ihn **ganz** nachbauen.

- [x] **Ein nicht-zylindrischer Durchbruch war in der Draufsicht
      unerreichbar** — behoben am selben Tag auf Roberts „mach das offen
      genannte auch", und **anders als hier zuerst stand**. Die Zeile darüber
      lautete: „Die allgemeine Fassung wäre der Strahl gegen die Dreiecke der
      Merkmale statt gegen einen Zylinder." Das löst den Fall nicht. Zwei
      Gründe, beide gemessen:

      * **Bei senkrechtem Blick liegen die Wände des Ausschnitts parallel zum
        Strahl.** Dort ist so wenig ein Dreieck zu treffen wie an der
        Bohrungswand — die teurere Rechnung hätte dasselbe `None` geliefert.
      * **Es gibt kein Merkmal zu wählen.** Ein rechteckiger Ausschnitt besteht
        aus vier `face`-Merkmalen, von denen keine „richtiger" ist als die
        andere. Ein Gewinner unter ihnen wäre erfunden, und `hole` ist der
        Gegenfall: Dort *ist* das Merkmal die Sache.

      Entschieden wird deshalb nicht „welches Merkmal", sondern „welcher
      **Körper**": Wer in eine Öffnung zeigt, hat auf das Teil gezeigt, und die
      Auswahl aufzuheben ist in jedem Fall falsch. `_through_aim` fragt die
      **konvexe Hülle** des Körpers (`geom.mesh.hull_planes`,
      `ray_span_in_hull`) — nicht den Hüllquader, denn der eines L-Profils
      reicht weit ins Leere und nähme die Zusage „ein Klick daneben hebt die
      Auswahl auf" (§18.5) mit. Gemessen am echten Picker, 60×40×8-Platte mit
      12×8-Ausschnitt, Draufsicht: 0 bis 30 px in der Öffnung **vorher
      `(None, None)`, nachher `('obj_1', None)`**; ab 60 px unverändert
      `face_2`. Kosten 0,03 ms beim ersten Aufruf, 0,015 ms danach.

      **Der Kostendeckel war die eigentliche Arbeit.** Die exakte konvexe Hülle
      von `dense_1m.stl` braucht **5084 ms** — bei einer feinen Kugel liegt
      jeder Punkt auf der Hülle, dieselbe Falle, die `SHADOW_HULL_POINTS` beim
      Schattenumriss schon kennt. Über eine Stichprobe von 4096 Punkten plus
      den äußersten in sechs Achsenrichtungen sind es **20 ms**, und an der
      Korpusplatte liefern beide Wege dasselbe: zwölf Flächen, Volumen
      32 000 mm³. Gerechnet wird über Halbräume und nicht über ein Hüllnetz —
      ein Strahl gegen 8202 Hülldreiecke wäre wieder das, was vermieden werden
      sollte.

- [x] **Die Textsuche der Suitenteilung fragt das falsche — geschlossen am
      28.08.2026.**
      `suite-getrennt.sh` sucht seine Fensterdateien mit
      `grep -lE "MainWindow|Viewport|pyvista"` — also „kommt das Wort vor?"
      statt „baut die Datei ein Fenster?". Der Grund dafür ist gut: Eine neue
      Fensterdatei soll keinen Eintrag brauchen. Der Preis ist heute zum
      **zweiten** Mal fällig geworden: `test_performance.py` sammelte in der
      Fenstergruppe nichts (Exit 5, steht in `CLAUDE.md`), und am 24.08. wanderte
      `tests/test_sketch.py` wegen des Wortes **in einem Docstring** aus der
      parallelen Sammelgruppe in die serielle Gruppe — 49 Tests, grün, aber
      seriell, und die Sammelgruppe fiel um 36 (3559 → 3523; eine zweite Sitzung
      maß am selben Tag 3554 → 3527, andere Zeitpunkte im geteilten Baum).

      Ironisch daran: Das Wort stand in einem Satz **über meinen eigenen
      Strahl** („Der Viewport reicht den Schritt von der nahen zur fernen Ebene
      herein"), geschrieben von der Nachbarsitzung über `_pick_ray`. Behoben ist
      der Einzelfall durch Umformulieren (`eefba3e9`), nicht die Ursache — und
      formwerk-9e hat den Satz dazu geliefert: *Zweimal dieselbe Falle heißt,
      dass die Suche zu grob ist, nicht dass zwei Leute unachtsam waren.*

      Ein engeres Muster (nur `import`- und Fixture-Zeilen) wäre dichter und
      trotzdem nicht dicht: Eine Datei, die ihr Fixture über `conftest.py`
      erbt, nennt keines der drei Wörter. Sauber wäre das Kriterium am
      **Fixture-Graphen** — was auf `qt_app` oder `window` zugreift, baut ein
      Fenster. Gemeldet von formwerk-48.

      `tools/list_windowed_tests.py` lässt pytest vollständig sammeln und
      nimmt genau die Dateien, deren aufgelöster Fixture-Graph `qt_app`
      enthält. `suite-getrennt.sh` liest diese Liste statt Quelltext. Der
      Werkzeugtest hält beide Richtungen fest: eine indirekte Fixture zählt,
      ein bloßes Wort im Docstring nicht.

      **Bewusst nicht mitgebaut:** eine Zielhilfe am Rand eines Ausschnitts.
      Bei der Bohrung meint ein Klick 0,4 mm neben der Kante die Bohrung, weil
      sie das Merkmal ist; neben einem Ausschnitt ist die Deckfläche das
      Merkmal, und die ist getroffen. Wer die Innenwand will, sieht sie von
      schräg — dann liegt dort ein Dreieck, und der Zell-Pick trifft es.


## Was niemand las, und was zweimal dastand (24.08.2026)

Zweiter Durchgang, diesmal mit anderen Fragen als beim ersten: nicht „welcher
Code steht doppelt", sondern „welcher Code wird nie gelesen" und „welche
Aussage steht an zwei Stellen, von denen nur eine wirkt". Dazu die zwei
Entscheidungen, die der erste Durchgang offen gelassen hat.

Vorweg wieder das Negative, weil es das Ergebnis mitträgt: **2985 Texte im
Quelltext, 2985 Einträge in jedem der fünf Kataloge, null verwaist, null
fehlend** — exakte Deckung. Alle Migrations-Beispieldateien werden geprüft
(`test_project.py:470` sammelt sie per Glob), alle Bausteine auch
(`test_parts.py` parametrisiert über `PARTS.all()`). Beide sahen in der ersten
Messung nach Lücken aus und waren keine: Wer per Glob sammelt, nennt keine
Namen — und ist damit besser dran als eine gepflegte Liste, weil ein neuer
Eintrag automatisch mitgeprüft wird.

- [x] **`positive` gehört in `_RANGE_CONSTRAINTS`** (`76c6dd13`). Der offene
      Punkt aus dem ersten Durchgang, entschieden: Die nach unten offene Spanne
      **ist** eine Spanne. „Dieses Maß muss größer als null sein" trug die
      Überschrift „Die Eingabe war so nicht verwendbar." — wahr, aber vage, und
      die Oberfläche zeichnet den Titel groß. Mit sechzehn Aufrufern über
      `require_positive` der häufigste der neun Fälle. Der Test prüft jetzt
      beides: die Liste und den echten Weg durch `require_positive`.

- [x] **Vier Meldungen, zwei Sätze** (`791a1576`). „Bitte zuerst ein Objekt
      auswählen." stand viermal in `main_window.py`, „Dafür braucht es einen
      Körper in der Szene." viermal. **Die Falle beim Zusammenlegen ist der
      eigentliche Ertrag:** `tr()` übersetzt sofort, eine Modulkonstante damit
      friert die Sprache des Imports ein — gemessen, nach `set_language("en")`
      liefert `str(_(…))` „Please select an object first.", ein zur Importzeit
      ausgewertetes `tr(…)` weiter den deutschen Satz. Und der naheliegende
      Ausweg (Satz als nackte Zeichenkette, an der Stelle `tr(KONSTANTE)`)
      wirft ihn aus allen fünf Katalogen, weil `i18n.extract` nur feste
      Zeichenketten liest. Beide Wege sehen richtig aus, keiner wird rot.

- [x] **Eine Sicherheitsliste, die niemand las** (`5c6e57a2`). `INCLUDING` in
      `openscad.py` zählt die neun Anweisungen auf, mit denen OpenSCAD etwas
      hereinholt, und liest sich wie die maßgebliche Liste der Prüfung nach
      Regel 11. Geprüft wird mit zwei regulären Ausdrücken, die dieselben Namen
      ein zweites und drittes Mal aufzählen. Gemessen deckungsgleich, es fehlte
      also nichts; die Gefahr lag in der Zukunft. Die Liste ist jetzt die
      Zusicherung — ein Eintrag ohne Prüfung ist ein roter Lauf. Nicht
      zusammengelegt, weil in einer Regex-Alternative die Reihenfolge trägt
      (`import` vor `import_stl` erreicht `import_stl` nie).

- [x] **Drei Konstanten, die niemand las** (`77ad37cb`). `SOLVER_CHAIN` in
      `types.py` war die dritte Aufzählung derselben Reihenfolge neben dem
      Literal `SolverStage` und `boolean.FULL_CHAIN` — entfernt. `ALIGN` in
      `header.py` war tot und nahm den `Qt`-Import mit. `BACKGROUND_MEGABYTES`
      und `WEIGHT_GIGABYTES` tragen Zahlen, die **von Hand** im Fortschrittstext
      stehen; dass das driftet, stand im Kommentar selbst (er sagte 444, die
      Konstante 445).

Was offen bleibt — und der erste Punkt ist eine **zurückgezogene Deutung**:

- [x] **Erledigt, mit einem anderen Ergebnis als erwartet** (3a,
      `bce88ff8`, 30.08.2026): Der Griff steht jetzt einmal
      (`leash.stop_watching_the_dying`) und wird an sieben Stellen
      gerufen. Gemessen schlägt er nur in `OverlayHost` an — 119 Mal in
      vier Millionen Filteraufrufen, die sechs anderen Stellen null Mal.
      Sie bleiben als **Vorsorge** für „ein Kind geht einzeln"; die
      Zählung `installEventFilter` gegen `removeEventFilter` war nie
      eine Aussage. Der ursprüngliche Wortlaut des Punkts bleibt
      darunter als Geschichte stehen:

      **Elf von dreizehn Eventfiltern werden nie abbestellt, und was das
      bedeutet, weiß ich nicht.** Das Zählverhältnis ist belegt:
      `installEventFilter` steht 13× in `app/ui`, `removeEventFilter` 2× —
      `survey.py:208` und `viewport.py:4183` machen es, `app.py:276` und
      `shortcut_schemes.py:158` installieren auf `application` und bestellen nie
      ab. **Die naheliegende Schlussfolgerung ist gemessen und hält nicht:** Ein
      Versuch, den Fehler mit einem aufgegebenen Filterobjekt nachzustellen,
      blieb fehlerfrei — Qt entfernt sterbende Filter selbst aus seinen Listen.
      Das Verhältnis bleibt ein Faktum ohne Folgerung, und es steht hier, damit
      niemand es ein zweites Mal für die Erklärung hält. Wer weitersucht, sucht
      die Zwischenlage: Python-Objekt halb abgebaut, C++-Seite lebendig — das
      ist der Fall, den `conftest.py` mit `isValid` behandelt.

      **Nachtrag vom 24.08.2026: die Folgerung ist da, und die Suchrichtung
      oben war richtig.** Der erste reproduzierbare Fall fiel an, als die
      Fenster sterben konnten (`acb0dd5`): Solange jedes an seinem `partial`
      hing, starb keines, und ein nie abbestellter Filter fiel nicht auf.
      `tests/test_first_run.py` ist auf dem Commit davor dreimal grün und
      danach in fünf Läufen dreimal rot — Teardown-Fehler, `OverlayHost` und
      `ObjectTree` mit abgeräumter C++-Seite.

      **Der Unterschied zur widerlegten Deutung ist die Richtung.** Stirbt das
      *Filterobjekt*, räumt Qt selbst auf — das war gemessen und hält. Stirbt
      das *überwachte* Objekt, läuft der Filter des Überlebenden in den Abbau
      hinein und fragt halb abgeräumte Geschwister nach ihrer Geometrie. Der
      Griff dagegen ist ``QEvent.Type.Destroy``, das Qt schickt, **bevor** die
      C++-Seite weg ist: `e0540a1` bestellt dort ab, drei Zeilen, und die Quote
      geht von vier von sechs auf null von sechs.

      **Was dabei nicht half, ist die Hälfte des Ertrags:** Zwei Wachen am
      Eingang von `_place` (`isValid` auf Wirt, Ansicht und Zonen) senkten die
      Quote nicht — drei bis vier von sechs blieben rot. Eine Prüfung am
      Eingang gewinnt keinen Wettlauf, der **während** des Aufrufs entschieden
      wird. Wer die übrigen elf angeht, fängt deshalb beim Abbestellen an und
      nicht bei `isValid`.

      Einer von dreizehn ist erledigt. Die übrigen stehen noch, und
      `app.py:276` sowie `shortcut_schemes.py:158` installieren auf
      `application` — die überleben alles und sind der andere Fall.

      **Zweiter Fundort, 30.08.2026, im ausgelieferten Stand:** Der Torlauf
      auf `17c4bebb` war rot an `tests/test_split_tool.py::
      test_a_click_beside_the_model_takes_the_old_line_with_it` —
      `AttributeError: 'QWidgetItem' object has no attribute 'rowCount'` aus
      einem `eventFilter` heraus (`overlay.py:294`). Einzeln grün, als Datei
      grün, auf `17c4bebb~1` ebenfalls grün — keine Regression, sondern
      dieselbe Familie: ein Filter, der während des Abbaus Nachbarn befragt,
      die keine mehr sind. Wer die elf angeht, nimmt diesen Fall als
      Reproduktionsversuch mit.

- [ ] **Wirkt die Typprüfung an `overlay.py:294`?** Der zweite Fund der
      Serie fällt aus einem anderen Grund als das Abbestellen — ein
      fremder Wrapper unter recyceltem Zeiger, gegen den `isValid`
      nichts sagt (`bce88ff8`, Gegenprobe reproduziert die
      Torlauf-Meldung wortgleich). Ob die Prüfung den echten Riss unter
      Last verhindert, zeigt erst der nächste volle Torlauf — bis dahin
      ist sie plausibel, nicht belegt.

      **Dritter Fundort, Release-Kontrolle vom 30.08.2026:** Im vollen
      Torlauf auf `4807f3f2` fiel `test_split_tool.py::
      test_a_changed_document_drops_the_line` — ein anderer Test als beim
      zweiten Fundort, dieselbe Zeile `overlay.py:294`, erreicht über
      `LayoutRequest` → `eventFilter` → `_place` → `rows_in` auf einem
      Nachbarn, der keiner mehr ist. Einzeln gefahren: 29 passed, Exit 0.
      Das einzige `F` des gesamten Torlaufs; die Familie meldet sich unter
      Last inzwischen an drei Tests derselben zwei Dateien.

- [x] **Drei Widgets bekommen Ereignisse, die ihr Zustand nicht mehr trägt**
      — als eigener Punkt aufgelöst, die Suche läuft anderswo weiter.
      Am 24.08.2026 in `test_ui.py` gemessen, alle drei im Teardown, alle drei
      einzeln grün: `shortcut_schemes.py:131` endet in einem `TypeError`,
      `overlay.py:587` findet `_placing` nicht, `viewport.py:4312` nicht
      `_drag_kind`. Die Initialisierungsreihenfolge ist bei allen dreien geprüft
      und in Ordnung — die Attribute werden im `__init__` gesetzt, der Filter
      erst danach installiert. Drei Sitzungen haben je einen Fall unabhängig
      gesehen, und das ist der Grund, warum es hier stand: Es ist kein
      Einzelfall.

      **Einer der drei ist erklärt, die anderen zwei nicht.** Der `TypeError` in
      `shortcut_schemes` ist die Folge von 4378 verschachtelten Frames in
      `NavigationKeys.eventFilter` — Einzelheiten bei „Fünf Fensterdateien
      reißen vor ihrer Zusammenfassung", wo auch die Messung wartet. Was die
      Kaskade auslöst, ist offen, und für `_placing` und `_drag_kind` gibt es
      bislang keine Erklärung; zwei naheliegende sind dort ausdrücklich
      widerlegt.

      Der Punkt ist trotzdem abgehakt: Er war eine Sammlung von Beobachtungen
      ohne eigene Frage, und die Frage steht jetzt an der Stelle, an der
      gemessen wird. Zwei Register-Einträge für dieselbe Suche wären einer zu
      viel — **und diese Zeile hat schon einmal zu viel behauptet:** Sie nannte
      die Sache am 24.08. „beantwortet" und berief sich auf ein Use-after-free,
      das am selben Tag zurückgezogen wurde.

- [x] **Zwei Downloadgrößen stehen im Text statt in der Message-ID** — und
      das bleibt so, aus einem anderen Grund als dem hier notierten.
      (Entschieden 27.08.2026, gemessen an den Katalogen.)

      Notiert war: Der Umbau koste fünf Übersetzungen für zwei Sätze, „und die
      kann keine Sitzung erfinden". Erfinden müsste sie auch niemand — die
      Sätze stehen längst in allen fünf Sprachen, ein Platzhalter hätte nur die
      Zahl ersetzt. Der wahre Grund steht in den Katalogen selbst:

          en: Loading weights — about 7.5 GB, this takes a while
          es: Descargando pesos: unos 7,5 GB, esto lleva tiempo
          fr: Téléchargement des poids — environ 7,5 Go, cela prend du temps
          it: Scaricamento dei pesi: circa 7,5 GB, ci vuole tempo
          pt: A carregar os pesos — cerca de 7,5 GB, isto demora

      **Jede Sprache schreibt die Zahl so, wie sie dort geschrieben wird** —
      Englisch mit Punkt, die vier romanischen mit Komma, und Französisch sagt
      „Go" statt „GB". Das kann sie nur, weil der ganze Satz übersetzt wird.
      Ein `{groesse}` an dieser Stelle bekäme seinen Wert aus dem Kern, und der
      formatiert überall mit Punkt (`{frei:.1f}` in derselben Datei, §6 rundet
      nur in der Anzeige). Aus „rund 7,5 GB" würde in vier Sprachen „rund 7.5
      GB". **Der Umbau wäre für den Kunden eine Verschlechterung**, und der
      Weg, den der Kommentar als den richtigen anführt, ist nur für ganze
      Zahlen der richtige.

      Was bleibt, ist die Driftgefahr, und die ist bereits abgesichert:
      `tests/test_mesh_backend.py::test_the_sizes_in_the_progress_text_match_the_constants`
      hält Konstante und Text zusammen, in beide Richtungen. Wer die Größe
      nachzieht und den Satz vergisst, bekommt einen roten Lauf — und muss dann
      fünf Katalogzeilen anfassen, was richtig ist, denn fünf Sprachen nennen
      die Zahl.


**Und ein Fund über das Suchen selbst.** Von den Verdachtsfällen dieses
Durchgangs waren mehr falsch als richtig: Die Bausteine ohne Test hatten einen
(per Parametrisierung), die Beispieldateien ohne Nennung auch (per Glob), drei
von vier `return {}`-Fällen waren korrekte Fallunterschiede, und die
Eventfilter-Deutung ist widerlegt. Was durchhielt, hielt durch, weil es **am
Code** belegt war und nicht an einer Zählung. Ein Suchmuster ist ein Vorschlag,
keine Aussage — und wer es nicht an einem Fall prüft, dessen Ausgang er kennt,
meldet Funde, die es nicht gibt.

## Zweitausend Verweise, und zwei ohne Ziel (24.08.2026)

Dritter Durchgang, und diesmal nicht gegen den Code, sondern gegen die **Doku im
Code**. Dieses Projekt erklärt außergewöhnlich viel in Kommentaren, und
Erklärungen altern schneller als Code: Sie werden von keinem Test gelesen und
von keinem Linter geprüft.

Drei Sorten Verweise sind hart prüfbar, und alle drei sind gemessen.

**Sphinx-Rollen** (`:func:`, `:class:`, `:data:`, `:mod:`): 102 Verweise auf
`app.*`, davon **einer** ohne Ziel — und der war ein Fehler der Messung, nicht
des Codes: `markup.py` verweist auf `app.core.registry.documentation`, und das
gibt es, nur als Lazy-Export aus `registry.surfaces`. Ein Prüfskript, das
`__getattr__`-Tabellen nicht auflöst, sieht es nicht.

**`Datei:Zeile`-Angaben:** drei im ganzen Baum, alle drei in `app/ui/leash.py` —
und alle drei zeigen heute auf andere Zeilen. Trotzdem kein Fund: Es ist ein
**datierter py-spy-Abzug** („Gefunden am 23.08.2026 in einem Stapelabzug"), also
die Aufnahme eines Zeitpunkts. Dass die Zeilen wandern, gehört dazu; wer den
Abzug liest, liest ihn als Geschichte. Ein Werkzeug hätte es als Mangel
gemeldet.

**§-Verweise auf den Bauplan:** 2214 Stück auf 110 Abschnitte, sieben ohne Ziel.
Fünf meinen ein anderes Dokument und sagen das — RFC 8032 bei Ed25519, ein
Konzeptpapier bei der Skelettsitzung. Zwei bleiben, und sie stehen unten.

- [x] **Ab jetzt kann kein neuer §-Verweis ins Leere zeigen** (`0ec51a0e`).
      `tests/test_plan_references.py` liest die numerierten Überschriften des
      Bauplans und hält alle Verweise aus `app/` und `tools/` dagegen; Zeilen,
      die ein anderes Dokument nennen (RFC, Konzept, ISO, DIN), sind ausgenommen.
      Dazu drei Wächter gegen die Schwächen, die ein solcher Test hat: einer
      prüft, dass das Überschriftenmuster überhaupt greift (**beim ersten Anlauf
      fand es sechs von 113 Abschnitten**, weil die Überschriften des Bauplans
      kein §-Zeichen tragen — ein Test gegen eine leere Menge ist immer grün),
      einer verlangt das Streichen aus der Ausnahmeliste, sobald ein Abschnitt
      entsteht, und einer ist die Gegenprobe.

- [x] **Zwei §-Verweise nennen Abschnitte, die der Bauplan nicht hat.** `§33.3`
      fünfmal (zweimal ausdrücklich „Bauplan §33.3", in `core/report.py` und
      `core/support.py`) — §33 führt 33.1 Ausnahmehierarchie und 33.2 Protokoll,
      der Fehlerbericht selbst steht in §37.2. `§25.4` einmal, am `caveat` eines
      Bausteins — §25 hat keine Unterabschnitte, und die Zeile darüber verweist
      auf §24.1, wo 24.1 bis 24.5 stehen. Ein Zahlendreher ist wahrscheinlich
      und nicht belegt.

      **Beides bleibt liegen, und zwar mit Grund.** Den Bauplan ändert nur
      Robert; die Verweise umzubiegen wäre geraten, weil nirgends steht, welcher
      Abschnitt gemeint war. Zwei Zeilen Aufwand, sobald die Frage entschieden
      ist.

      **Entschieden und umgebogen am 26.08.2026** (Roberts Pauschal-Freigabe
      vom 25.08., „alles perfekt für Kunden machen"): §33.3 heißt an allen
      fünf Stellen §37.2 — der Fehlerbericht wohnt dort, das ist kein Raten
      mehr, seit §37.2 ihn ausdrücklich führt —, der `caveat` verweist auf
      die Familie §24, und `BEKANNT_OFFEN` in `tests/test_plan_references.py`
      ist leer. Der Bauplan selbst blieb unangetastet; neue Abschnitte
      entstehen keine.

**Und ein Wort über die Werkzeuge dieses Durchgangs**, weil es das dritte Mal
dasselbe ist: Von den vier Messungen lieferten zwei zunächst ein falsches Bild —
der Sphinx-Prüfer meldete einen Mangel, den es nicht gibt (Lazy-Export nicht
aufgelöst), und der §-Prüfer fand sechs von 113 Abschnitten, weil er ein Zeichen
erwartete, das die Überschriften nicht tragen. **Ein Prüfwerkzeug, das zu wenig
findet, ist gefährlicher als eines, das zu viel findet:** Zu viel kostet
Prüfzeit, zu wenig erzeugt die Gewissheit, es sei nichts da. Beide Male hat erst
ein Fall, dessen Ausgang schon bekannt war, das Werkzeug entlarvt.

## Ein Test, der auf einer Maschine nie grün war (24.08.2026)

Ein Abschlusslauf auf `b2bebed4` in einem eigenen Arbeitsbaum — ohne die
Zwischenstände der vier parallel arbeitenden Sitzungen — meldete **3 failed,
5489 passed, 24 skipped**. Kein `worker crashed`, also echte Fehler, und einzeln
nachgefahren blieben alle drei rot. `ruff`, `ruff format` und `mypy` sind grün.

- [x] **`test_style` war auf dieser Maschine seit seiner Einführung rot**
      (behoben in `5cb6e1ff`).
      `test_a_primary_button_is_wide_enough_for_its_own_bold_label` prüft, ob ein
      Hauptknopf breit genug für seine halbfette Beschriftung ist — die Zusage
      ist richtig und der Fehler, den sie verhindert, ist echt („etzt trenne" auf
      dem Trennknopf). Der **Vergleich** trägt sie nicht: Gehalten wird
      `QPushButton.sizeHint()` gegen `drawn + 2 * ROOMY`, und `ROOMY` ist der
      Innenabstand aus dem Stylesheet, das im Test niemand anwendet. Qt rechnet
      seinen eigenen.

      Gemessen auf dieser Maschine (`Sans Serif` 9 pt, offscreen): **alle fünf
      Texte scheitern, und zwar um konstant 10 Bildpunkte** — „Jetzt trennen"
      170 gegen 180, „Slicen" 86 gegen 96. Dass auch die kurzen scheitern, ist
      der Beleg: Es ist keine Textlänge, sondern eine feste Differenz zwischen
      zwei Innenabständen.

      **Gegengeprobt auf `49d4c731`, dem Commit, der ihn eingeführt hat: dort
      ebenfalls rot.** Der Test war auf dieser Maschine also nie grün, und die
      schreibende Sitzung hat ihn auf ihrer grün gemessen (ihr Kommentar nennt
      77 gegen 89 Bildpunkte, hier sind es 156 gegen 170). Damit ist es dieselbe
      Familie wie die maschinenabhängigen Bestwerte, die deshalb nicht im
      Repository liegen — nur diesmal in einem Test, der eine Zusage trägt.

      Zu entscheiden ist nicht der Zahlenwert, sondern **wo** geprüft wird: an
      einem nackten `QPushButton` ohne Stylesheet lässt sich die Frage nicht
      stellen. Am gebauten Fenster mit angewandtem Stylesheet schon.

      **Genau so behoben** (`5cb6e1ff`, von Robert beauftragt, nachdem diese
      Messung vorlag; `formwerk-9e` hat `style.py` und `test_style.py`
      freigegeben und das Vorbild mitgeliefert). Gemessen wird jetzt **mit
      angewandtem Thema**: „Jetzt trennen" bekommt damit 182 statt 170
      Bildpunkte und braucht 180. **Die Schwelle ist unverändert geblieben** —
      ein Test, dessen Zahl man verschiebt, bis er grün ist, prüft nichts mehr.

      Das Vorbild stand im Bestand: `tests/test_sketch_editor.py` misst die
      Breitengrenze der Skizzenleiste seit je mit Thema, und sein Docstring
      nennt die **Gegenrichtung** desselben Fehlers — ein Test, der zwei Runden
      grün war, weil ihm die Polsterung fehlte. Dieselbe Ursache, zwei
      Vorzeichen: Das Stylesheet gehört zur Messung und nicht zur Kulisse.

- [x] **Handbuch und Website hinkten dem Register nach** (behoben in
      `b9460ffd`).
      `test_the_website_page_carries_the_generated_reference` ist für `de` und
      `en` rot: `520b10f0` hat zwei Gewindetitel geändert
      (`insert_printed_thread`, `thread_exact`), und `website/handbuch.html` samt
      `website/en/manual.html` stammen von `7cc07342`. Der Test nennt den Fix
      selbst — `tools/make_manual.py`.

      Liegen geblieben, weil `formwerk-48` noch drei weitere Pakete mit
      Titeländerungen vor sich hat und jede den Test wieder rot macht: **ein Lauf
      am Ende ist billiger als vier dazwischen.** Abgesprochen.

      Der Fund gehört zur Hälfte hierher, weil der Vorschlag für die neuen Titel
      aus dieser Sitzung kam — und die Folge, dass ein Registertitel in zwei
      erzeugte HTML-Dateien reicht, stand in dem Vorschlag nicht. „Was kostet es
      an anderer Stelle" ist bei erzeugten Dateien leicht zu übersehen, weil sie
      im Diff nicht auftauchen, solange niemand das Werkzeug laufen lässt.

---

## Ein Haken für eine Lochplatte, deren Maße niemand kennt (24.08.2026)

Ein Kunde fragte am 24.08.2026, ob man an ein heruntergeladenes Modell IKEA-
SKÅDIS-Haken hängen kann, ohne es nachzukonstruieren. Die Antwort ist zweimal
nein und einmal fast: Den Baustein gibt es nicht, seine Maße kennen wir nicht,
und der Ablauf drumherum steht bis auf einen Handgriff.

Das Konzept liegt in `konzepte/konzept-befestigungssysteme-2026-08.md` und
nennt acht Arbeitspakete, die Abnahmekriterien und das, was ausdrücklich nicht
gebaut wird. Hier stehen die zwei Punkte, die es zu Arbeit machen.

- [x] **Der Einhänger für Lochwände** als Baustein `pegboard_hook` in der
  Gruppe „Befestigung", mit dem Raster als neuer Tabellenart in
  `standards.toml`. Vorher steht das Messen: Die Lochung einer SKÅDIS-Platte
  ist nirgends belastbar dokumentiert — `dimensions.com` nennt nur die
  Außenmaße, die Modellportale nennen Zahlen ohne Herkunft und widersprechen
  sich in der Plattendicke (3, 5 und 5,2 mm). Ein Zapfen, der um einen halben
  Millimeter danebenliegt, geht in kein Loch von fünf. Also wird an einer
  echten Platte gemessen, bevor eine Zeile entsteht, und der Wert kommt mit
  Datum und Herkunft in die Tabelle (§24.2).

  **Gemessen am 27.08.2026** (Alexander Schneider, Messschieber, eine Platte;
  weitere angekündigt): Schlitzbreite 4,9–5,1, Schlitzhöhe 14,9–15,1, über
  zwei benachbarte Schlitze außen 45,0. Die 45,0 sind Raster plus eine
  Schlitzbreite und bestätigen die hinterlegten 40,00 — von drei möglichen
  Deutungen trifft nur diese das Rastermaß, die anderen ergäben 45,0 oder
  50,0.

  **Kein Nennwert war zu korrigieren, und das war nicht der Ertrag.** Neu ist
  die **Toleranz von ±0,1 mm**, und die hat keine Zeichnung. Sie ist genau der
  Grund, aus dem der Zapfen sein Spiel aus dem Materialprofil bezieht: im
  engsten gemessenen Schlitz bleiben unter PETG 0,15 mm Luft, unter PLA 0,10.
  `test_the_hook_still_fits_the_narrowest_slot_that_was_measured` hält das für
  vier Materialien fest und misst gegen die **untere** Grenze, denn nur sie
  kann klemmen; nimmt man dem Zapfen sein Spiel, fallen alle vier
  (`7ace4b14`).

  **Offen bleibt allein die Plattendicke** — ausgerechnet die einzige der fünf
  Zahlen, die nie belegt war („approximate; the exact decimal is unverified")
  und aus der etwas folgt: Die Nasentiefe des Einhängers ist zwei Drittel
  davon. Die vier gemessenen Werte standen schon auf der Zeichnung, dieser
  nicht.

- [x] **Additive Bausteine erscheinen am Flächenklick** (`074e5d0` und
  `73cc2f6`, 24.08.2026). Der Befund von damals lautete:
  `parts/ops.py:_applies_to` nimmt `"face"` nur auf, wenn ein Baustein
  abträgt. Gemessen über alle achtzehn: `wall_mount`, `profile_tongue`, `rib`,
  `snap_fit`, `latch` und `living_hinge` tragen `applies_to == []` — mit den drei Prüfkörpern neun von achtzehn — und stehen
  damit in keinem Kontextmenü einer angeklickten Fläche. Der Rückfall in
  `panels.py:context_menu` greift nicht, denn er greift nur, wenn die
  Merkmalsart **gar nichts** anbietet — eine Fläche bietet die abtragenden an.
  Wer also auf die Rückseite eines Modells zeigt, um einen Wandhalter zu
  setzen, findet dort alles außer dem Wandhalter. §18.5 nennt genau dieses
  Menü „die wichtigste Einzelfunktion". Der Punkt ist älter als die
  Kundenanfrage und wird unabhängig von ihr behoben.

  **Behoben, und die Reihenfolge war der Ertrag.** Der naive Fix — additive
  Bausteine einfach an `face` — hätte den Flächenklick von 19 auf 26
  Operationen gebracht und damit verschlimmert, was er verbessern sollte.
  Gemessen wurde deshalb zuerst das Menü selbst, und dort lag ein zweiter,
  größerer Befund: Es faltete **alles** in Untermenüs, sobald die Zeilengrenze
  überschritten war, und damit kostete jede Operation zwei Klicks — auch die
  Bohrung, die zu zweit in „Erzeugen" stand. Die Regel dagegen steht seit je
  in `registry.surfaces.group_is_flat` für die Menüleiste; das Kontextmenü
  kannte sie nicht.

  Jetzt faltet es von der größten Gruppe abwärts und nur so weit, bis der Rest
  passt (`folded_groups`, ohne Qt und deshalb ohne Fenster prüfbar). Und die
  Zuordnung steht in der Deklaration statt in einer Ableitung: `at_face`,
  Vorgabe wahr, die drei Prüfkörper abgemeldet — dieselbe Bauart wie `at_hole`
  daneben, dessen Docstring genau diese drei schon als Fall nennt, der
  nirgends hingehört.

  Der Flächenklick steht damit so: 26 Operationen, neun direkt, ein Untermenü
  „Bausteine" mit acht direkten Einträgen und zwei tieferen Gruppen. Kein Menü
  über zwölf Zeilen, und der Wandhalter ist in zwei Klicks erreichbar statt
  gar nicht.

---

## Die Haftungsgrundlagen des Geschäftsmodells nachkontrolliert (24.08.2026)

Robert hat die Haftungsgrundlagen des Geschäftsmodells noch einmal prüfen
lassen. Der damalige Förderentwurf ist inzwischen durch eine PayPal-Spende
ohne Gegenleistung ersetzt; hier stehen die Befunde, die für Demo oder Verkauf
trotzdem Arbeit sind.

**Der Anlass, in einem Satz:** Die damalige Prüfung hatte die
Haftungsklauseln der EULA als „fachlich solide aufgebaut" abgehakt und die
Rechtsformentscheidung darauf gebaut. Der Aufbau stimmte — der Wortlaut nicht.

**Und einer der Punkte gilt heute und nicht erst zum Verkaufsstart:** `AGB.md`
setzt sich für die Demo-Zeit selbst außer Kraft, der Verkauf ist bis zum
30.10.2026 zu. Damit ist `EULA.md` Nummer 4a die **einzige Haftungsregelung mit
heutiger Wirkung** — und die schwächste der drei.

- [x] **Zwei Sätze in der EULA tragen nicht, was auf sie gebaut wird.**
      Nummer 11 sagt „**wir** haften unbeschränkt bei Vorsatz und grober
      Fahrlässigkeit" und schließt danach jede weitergehende Haftung aus;
      § 309 Nr. 7 lit. b BGB verlangt dieselbe Ausnahme für **gesetzliche
      Vertreter und Erfüllungsgehilfen**. AGB werden nicht geltungserhaltend
      reduziert — fällt die Klausel, fällt sie ganz, und dann gilt die volle
      gesetzliche Haftung.

      Nummer 4a begrenzt für die Demo auf Vorsatz und grobe Fahrlässigkeit,
      was Körperschäden bei einfacher Fahrlässigkeit ausschlösse (§ 309 Nr. 7
      lit. a), und verweist im selben Atemzug auf Nummer 11, die das Gegenteil
      sagt. Dazu die Prämisse: Eine Demo wird zur Absatzförderung überlassen,
      nicht aus Freigebigkeit — das Privileg des § 521 BGB ist damit nicht
      selbstverständlich zu haben.

      **Der Fix ist klein** — fünf Wörter in Nummer 11, ein ersetzter Satz in
      Nummer 4a —, aber es ist ein Rechtstext: Fassungsnummer hoch,
      `tools/make_legal.py` neu laufen lassen, hochladen. **Robert
      vorzulegen.**

      **Erledigt, festgestellt am 26.08.2026:** Fassung 1.2 vom 24.08.
      (`230e4985`) trägt beides längst — Nummer 11 nennt gesetzliche
      Vertreter und Erfüllungsgehilfen an beiden Stellen, 4a verweist ohne
      Abstriche bei Leben, Körper und Gesundheit auf die Nummern 10 und 11 —
      und `website/eula.html` wie `packaging/eula.txt` sind auf 1.2 erzeugt.
      Roberts Freigabe vom 25.08. deckt die Fassung; offen ist allein der
      nächste Website-Upload, der die erzeugte Seite mitnimmt.

- [ ] **Die Versicherung trägt die Rechtsformentscheidung und steht in keiner
      Liste.** Die Entscheidung für das Einzelunternehmen setzt voraus, dass
      das nicht ausschließbare Produktrisiko versichert wird. Dafür fehlt noch
      ein Angebot.

      Und sie muss anders aussehen als der Nebensatz vermuten lässt: Eine
      IT-Berufshaftpflicht deckt typischerweise **Vermögensschäden**. Personen-
      und Sachschäden aus einem fehlerhaften Produkt brauchen eine
      **Produkthaftpflicht mit Software-Einschluss** — Richtlinie
      (EU) 2024/2853 macht Software ausdrücklich zum Produkt, nimmt Datenverlust
      auf, streicht den Selbstbehalt und lässt sich nicht abbedingen.
      Umsetzungsfrist **09.12.2026**; der Verkaufsstart liegt danach. Zu fragen
      ist auch, ob die Police Schäden aus KI-gestützten Ausgaben einschließt und
      wie sie den Fall behandelt, dass ein Kunde sich **nicht** an Nummer 10
      hält.

- [ ] **Der Haftungsausschluss der EULA wirkt nur mit einem Häkchen im
      Bestellvorgang.** Nummer 10 — kein Prüfinstitut, keine zugesicherte
      Maßhaltigkeit, keine tragenden Teile — ist gegenüber Verbrauchern eine
      negative Beschaffenheitsvereinbarung. Nach § 327h BGB wirkt sie nur, wenn
      der Verbraucher davon **eigens** in Kenntnis gesetzt wurde und die
      Abweichung **ausdrücklich und gesondert** vereinbart ist. Ein Abschnitt in
      einem Vertragstext ist beides nicht.

      Der PayPal-Spendenweg verspricht keine Vorabversion und keine andere
      Gegenleistung. Der Punkt betrifft deshalb nur den späteren Verkauf.

- [x] **Für die PayPal-Spende ist keine eigene Kündigungsschaltfläche nötig.**
      Der alte Befund hing an einem monatlichen Stufenmodell mit geschuldeten
      Gegenleistungen. Dieses Modell ist gestrichen. § 312k Abs. 1 BGB setzt
      ein Dauerschuldverhältnis voraus, das den Unternehmer zu einer
      **entgeltlichen Leistung** verpflichtet; die PayPal-Spende ist
      ausdrücklich eine unentgeltliche Zuwendung ohne Gegenleistung. PayPal
      lässt wiederkehrende Spenden außerdem in den Profileinstellungen ändern
      oder beenden. Website, AGB, Widerrufsseite und Datenschutz erklären diese
      Grenze seit dem 28.08.2026 unmittelbar am Zahlungsweg.

- [ ] **Was der Zahlungsdienstleister vorn abnimmt, holt er hinten zurück.**
      Ein Merchant of Record nimmt beim späteren Lizenzkauf Umsatzsteuer,
      Rechnung, Widerruf und Streitfälle ab. Seine Verträge enthalten
      regelmäßig eine
      **Freistellungsklausel** zulasten des Verkäufers, häufig der Höhe nach
      unbegrenzt, nach fremdem Recht und mit fremdem Gerichtsstand.
      `EULA.md` Nummer 11 wirkt gegenüber dem Kunden, nicht gegenüber dem
      Dienstleister.

      Bei einem Einzelunternehmen haftet dafür das Privatvermögen. Das ist die
      größte vertragliche Haftungsübernahme des ganzen Modells, und sie steht in
      einem Vertrag, den noch niemand gelesen hat — zu lesen, bevor er
      unterschrieben wird.

---

## Ein eigener Baustein verlangt, dass der Kunde Python schreibt (24.08.2026)

§24.5 ist gebaut und wird benutzt: `parts/user.py` liest
`<Nutzerdaten>/parts/*.py`, macht aus jedem Fund eine Operation, kennzeichnet
sie im Katalog und hält ihren Abdruck im Dokument fest. Was fehlt, ist der
Schritt davor — heute ist ein eigener Baustein eine Python-Datei mit
`@register_part`, einer Parameterklasse und einer Funktion gegen
`manifold3d`. Wer das schreiben kann, braucht Solidon nicht; wer es nicht
kann, ist der Kunde, für den es gebaut wird.

Der Entwurf steht in `konzepte/konzept-befestigungssysteme-2026-08.md`
Teil II: Ein eigener Baustein ist ein **Rezept** — ein Ausschnitt des Stapels
plus die Beschreibung seiner Parameter, gespeichert als Daten. Sechs
Arbeitspakete, die Grenzen und die eine Entscheidung stehen dort.

- [x] **Eigene Teile aus der Anwendung heraus in den Katalog**, mit Titel,
  Einheit, Grenzen, Vorgabe und Beschreibung je Parameter — dieselben Angaben
  wie ein eingebauter Baustein, an derselben Stelle im Dialog. Dazu gehört,
  dass der Bereichstest aus §24.3 in die Anwendung wandert: „Ein Baustein ohne
  diesen Test gilt als nicht vorhanden", und `corners()` ist gewöhnlicher
  Code, kein Testwerkzeug.

  **Entschieden am 24.08.2026 (Robert): Ein Rezept darf in Projektdateien
  mitreisen.** Regel 13 schützt jetzt ausdrücklich vor *ausführbarem Code* und
  nicht vor Bausteinen an sich; §24.5 nennt die Unterscheidung. Drei Folgen
  stehen im Konzept (Abschnitt 17.1), und die erste ist mit dem Ausbau von
  OpenSCAD am 26.08.2026 **entfallen**: Sie band die Quelltextprüfung aus §32
  an einen `create_from_scad`-Schritt im Rezept, und den gibt es nicht mehr —
  §24.5 trägt seither die allgemeine Fassung, das Konzept nennt sie noch in
  der alten. Es bleiben zwei: Ein mitgereistes Rezept überschreibt **nie**
  einen gleichnamigen eigenen Baustein, sondern wird umbenannt und als
  mitgereist gekennzeichnet; und die Version eines Rezepts ist der Hash über
  seine Daten.

- [x] **Behoben am 26.08.2026 mit `410bdb06`.** Der Verlauf nimmt Strg- und
  Umschalt-Klick, `HistoryPanel.selected_operations()` gibt die gewählten
  Schritte aufsteigend und ohne Doppelte heraus, und `_save_as_part` reicht
  sie durch. Leere Auswahl heißt weiterhin „ganzer Stapel" — das ist der
  häufige Fall und steht seit dem Umbau ausdrücklich im Dialog, statt
  stillschweigend zu gelten (`scope_text`, §2.4).

  **Eine Sammelzeile brauchte eine zweite Datenrolle.** Eine Transaktion aus
  vier Schritten trägt keine `UserRole` — ein Doppelklick könnte dort keine
  einzelne Operation zeigen —, und über sie wäre eine gewählte Sammelzeile
  stumm leer geblieben. `OPS_ROLE` beantwortet die andere Frage: was gehört zu
  dieser Zeile. Wer „Teilung in vier" wählt, meint alle vier.

  **Die Frage nach den Lücken ist entschieden, und zwar gegen eine Regel im
  Dialog.** Ein Ausschnitt aus Schritt 3 und 7 ohne 4 bis 6 kann sinnvoll sein
  — wenn die Zwischenschritte einen anderen Körper betreffen — oder unsinnig;
  welches von beidem, weiß der Bereichstest in `capture`, der ohnehin vor dem
  Speichern läuft und sagt, was herauskommt. Eine Regel im Dialog müsste
  dieselbe Frage schlechter beantworten und dabei den gültigen Fall
  verbieten.

  Drei Tests, und der dritte ist der, der die Lücke schließt: Auswahl und Satz
  wären beide grün, während das Fenster weiter alles übergibt — genau so ist
  am 25.08.2026 der `enumerate`-Fehler durchgekommen. Beide Gegenproben
  gefahren.

- [x] **Der Umbau ist längst gebaut** — nachgesehen am 26.08.2026, weil dieser
  Punkt als offen im Register stand. `bootstrap.user_operations()` sammelt,
  was aus dem Nutzerordner kam, `menu_tree(skip=…)` lässt es aus der
  Menüleiste heraus, und `MainWindow` reicht das eine ins andere. Erreichbar
  bleiben die Bausteine über Katalog, Befehlspalette und Kontextmenü, und
  `test_a_part_of_the_users_own_never_reaches_the_menu_bar` prüft das am
  **gebauten Fenster** statt an der Funktion darunter — durchgereicht ist
  nicht gerufen.

  Ein Punkt, der als offen dasteht, kostet einen Nachmittag, an dem jemand
  etwas baut, das es gibt. Genau davor warnt `CLAUDE.md`: „Wer ‚offen‘ in
  einem Konzept liest, prüft es am Code, bevor er es glaubt."

- [x] **Was daran wirklich fehlte, war die andere Seite: die
  Verfügbarkeit.** Behoben am 26.08.2026. Wer aus der Menüleiste
  herausgenommen wird, hat keine Menü-Action mehr — und
  `_palette_availability` las die Sperre genau daraus: `action is None` ergab
  „erlaubt". Für jeden eigenen Baustein hätte die Befehlspalette damit auf
  **leerer Szene** „geht" gesagt und den Kunden in die modale Sackgasse
  geschickt, gegen die `_run_palette_choice` gebaut wurde. Gerechnet wird
  jetzt über `_reason_locked` — dieselbe Funktion, die auch den Menüeintrag
  ausgraut, also keine zweite Quelle.

  Der Umbau hat den Fehler nicht verursacht, er hat ihn **freigelegt**: Die
  Annahme „jede Operation hat einen Menüeintrag" stimmte schon vorher nicht,
  seit die Zwillinge zusammengelegt sind. Sie fiel nur niemandem auf, solange
  es zwei Fälle waren statt zwanzig.


**Gebaut, und zwar vollständig — gemessen am 27.08.2026, nicht gelesen.** Das
Konzept führt in Teil II sechs Arbeitspakete, und eine Sitzung wollte sie
gerade unter drei Sitzungen aufteilen. Alle sechs stehen bereits:

| Paket | Beleg im Code |
|---|---|
| E1 Katalog statt Menü | `main_window.py` baut das Menü mit `menu_tree(skip=bootstrap.user_operations())`; der Kommentar dort nennt „Konzept Befestigungssysteme E1" wörtlich |
| E2 Rezeptformat | `parts/recipe.py`: `FORMAT_VERSION`, `fingerprint` — der Hash **ist** die Version (§24.4), und das Rezept reist über die Migrationen des Dokuments |
| E3 Bereichstest in der Anwendung | `parts/range_check.py` hat `corners()`; `tests/test_parts.py` ist nur noch ein Adapter darauf, mit „Eine Regel, ein Ort" im Docstring |
| E4 „Als Baustein speichern" | `app/ui/recipe_dialog.py` `RecipeDialog`, `main_window._save_as_part`; 32 + 34 Tests |
| E5 Rezept auswerten | `recipe.py` `build()`, `built()`, `build_with_profile()` — der `PartFn`-Ersatz |
| E6 Der Durchlauf | `tests/test_recipes.py::test_the_whole_way_from_an_imported_model_to_a_reused_and_changed_part`, mit den Schritten 4 bis 7 einzeln benannt |

Und es ist nicht bloß vorhanden, sondern **angeschlossen und geprüft**:
`tests/test_interface_limits.py` prüft das gebaute **Fenster** statt der
Funktion darunter — mit „Durchgereicht ist nicht gerufen" im Docstring und
einer Gegenprobe, weil der erste Anlauf grün gegen eine leere Menge war.
`tests/test_catalog_ui.py` prüft, dass ein eigener Baustein im Katalog als
solcher gekennzeichnet ist. Die Parameterangaben aus dem Kästchen oben —
Titel, Einheit, Grenzen, Vorgabe, Beschreibung — setzt `recipe.py` beim Bauen
des Schemas alle fünf.

**Der Grund, warum es hier zwei Tage zu lange offen stand**, ist der, vor dem
`CLAUDE.md` warnt: Die Konzepte tragen Statustabellen, und die altern. Von
zwölf Punkten, die sie am 22.08.2026 als offen führten, waren sieben behoben;
hier waren es sechs von sechs. Wer ein Arbeitspaket aus einem Konzept nimmt,
misst zuerst — zehn Minuten `grep` gegen eine Nacht Doppelarbeit.
---

## Zehn von zehn Fenstern überlebten ihr Loslassen (24.08.2026)

**Behoben mit `acb0dd5`; der Haken und die Zahlen stehen unten.** Dieser
Absatz stand bis zum 25.08.2026 im Präsens und behauptete damit fünfzig Zeilen
lang das Gegenteil dessen, was am Ende des Abschnitts abgehakt ist — zwei
Sitzungen haben ihn nacheinander als offenen Punkt gelesen und den Fehler
gesucht, den es nicht mehr gab. Eine davon hat ihn dann noch einmal
bisektiert. **Ein Abschnitt, der einen behobenen Fehler im Präsens erzählt,
ist ein offener Punkt für jeden, der ihn liest.**

`tests/test_widget_lifetime.py::test_a_released_widget_is_actually_released`
**war** auf `main` rot, und zwar in der Ausprägung `MainWindow`: **10 von 10
überlebten ihr Loslassen**. Gemessen am 24.08.2026 von zwei Sitzungen
unabhängig — einmal im geteilten Arbeitsbaum, einmal in einem eigenen Baum auf
`230e498` ohne fremde Änderungen. Es war keine der damals laufenden Arbeiten.

**Zur Zahl daneben, damit sie niemanden zweimal aufhält.** Die Datei sammelt
**42** Tests, die Ausprägungsliste dieses einen Tests umfasst **41**
Widget-Klassen, und der zweiundvierzigste ist der zweite Test der Datei. Wer
nur den Test fährt, liest „1 failed, 40 passed"; wer die Datei fährt, liest
„1 failed, 41 passed". Beides ist dasselbe Ergebnis. Die Differenz kostete
zwei Sitzungen einen Abgleich, bevor eine Zahl hier stand — **eine Zählung
ohne ihren Umfang ist keine.**

**Warum das ein eigener Punkt ist und kein Wiederaufmachen.** Der Punkt „Kein
Viewport wird jemals freigegeben" steht abgehakt in dieser Datei und trägt
seit dem 23.08.2026 den Vermerk „überholt, nicht erledigt — der Test prüft
`Viewport` und `MainWindow` und ist grün, seit er 41 Klassen baut statt 14".
Genau diese Zusage hält nicht mehr. Der alte Eintrag bleibt, wie er ist; seine
Geschichte gehört zu ihm.

**Alle zehn, nicht einige.** Das unterscheidet den Fall von den Messungen, die
damals danebenstanden (vier von fünfzehn, zwei von fünfzehn). Wo jede einzelne
Instanz überlebt, wartet niemand auf einen Zufall — da hält etwas fest, und
zwar immer.

**Die Frage ist beantwortet** (24.08.2026, 3d-druck-61 per `git bisect run` mit
`pytest -k MainWindow` als Probe, 2,3 s je Schritt). Erster roter Commit:
`f43284f` „Ein Menüeintrag, der keiner Operation gehört". Die Zeile ist
`app/ui/main_window.py:2240`, in `_add_variant_entries` und damit im Menüaufbau
**jedes** Fensters:

    partial(self.run_operation, first)

**Der Beleg stand die ganze Zeit in unserer eigenen Regel.**
`.claude/rules/oberflaeche.md` führt eine gemessene Tabelle, je zehn Objekte
losgelassen: `connect(self.rebuild)` überlebt 0 von 10,
`connect(partial(self.rebuild, 1))` überlebt **10 von 10** — mit dem Vermerk,
`functools.partial` helfe nicht, obwohl es wie die saubere Fassung eines
Lambdas aussieht, denn es hält die gebundene Methode und damit `self`. Die Zahl
der Tabelle ist exakt die des roten Tests. Nachgeprüft am 24.08.2026: Die Zeile
steht dort, sie ist der einzige solche Aufruf im Menüaufbau, und `weak_slot`
(`app/ui/leash.py:300`) wird in derselben Datei bereits 29-mal benutzt. Das
`partial` ist der Ausreißer, der Fix ist Hausstil und keine Umstellung.

- [x] **Die eine Zeile umgestellt, und sie war der einzige Halter**
  (`acb0dd5`, 24.08.2026):

      weak_slot(self, MainWindow.run_operation, first)

  **Gemessen, nicht angenommen** — und in einem eigenen Arbeitsbaum, weil der
  geteilte gerade fremde unfertige Arbeit trug: vorher 1 failed / 40 passed,
  nachher **41 passed**, zweimal. Danach dieselbe Messung mit *allen*
  uncommitteten Änderungen der anderen Sitzungen eingespielt: **42 passed**.
  Der Fix trägt also auch neben ihrer Arbeit, und die Sorge aus der Regel —
  beim Hauptfenster sei der letzte Halter erst nach 27 umgebauten Lambdas
  gefunden worden — hat sich hier nicht bestätigt.

  Nebenbei behoben: `weak_slot` verwirft mit seiner Vorgabe `forward=False` das
  `checked`-Bool, das `QAction.triggered` sendet. Bisher landete es als zweites
  Argument in `given` — bei einem Menüeintrag ohne Häkchen immer `False` und
  damit folgenlos, aber es stand da.

---

## Drei Stunden gegen ein Programm, das die richtige Adresse nicht annahm (24.08.2026)

Aus einer Rückmeldung zu 0.1.4: Ein Kunde wollte den Chat auf sein lokales
Ollama umstellen, hat drei Stunden gebraucht und es nicht geschafft. Er hat
dabei **nichts falsch gemacht** — jeder seiner Schritte war richtig, und jeder
lief in eine andere Stelle unseres Codes. Der Fragebogen kam ihm nach dreißig
Minuten dazwischen; er hat trotzdem freundlich geantwortet und um eine Anleitung
gebeten.

**Die Kette, aus dem Protokoll gelesen und am Code belegt:**

| Was er tat | Was das Programm tat |
|---|---|
| etwas ins Anthropic-Schlüsselfeld getippt | speichert es — ab hier ist Ollama unerreichbar |
| Chat benutzt | fragt Anthropic, `invalid x-api-key`, meldet „Das Sprachmodell hat nicht geantwortet" |
| Ollama-Adresse `http://127.0.0.1:11434` eingetragen | Anfragen gehen an die Wurzel → **405**, vierzehnmal im Protokoll |
| den Modellpfad ins Adressfeld gesetzt | Absturz: `Port could not be cast to integer` |
| die Fehlermeldung ins Schlüsselfeld kopiert | Absturz: `Invalid header value`, Fehlerbericht ging hinaus |

> **Alle fünf erledigt am 24.08.2026 (`335c204`).** Robert hat entschieden:
> „mach alles sauber" — also auch den Punkt, der als Verhaltensfrage
> vorgelegt war. Der Chat fällt jetzt nach einem `401`/`403` auf das nächste
> Modell zurück. 14 neue Tests, Übersetzungen in allen fünf Katalogen; im Tor
> 3637 grün, und die vier Auffälligkeiten des Laufs sind alle vorbestehend oder
> Abrisse beim Abbau. **Ausgeliefert ist damit nichts** — die Fixes gehen mit
> dem nächsten Paket hinaus, und dem Kunden ist der Weg von Hand beschrieben.
>
> **Zwei Reviews danach kam eine zweite Runde (`3b3114e`), und die eine Hälfte
> davon war ein halber Fix.** `3d-druck-61` hat nachgesehen, wo der
> Windows-Pfad überall ankommt: `http.client.InvalidURL` erbt von
> `HTTPException` und damit **weder von `ValueError` noch von `OSError`** —
> gefangen war er an einer von vier Stellen. Wer den Kommentar daneben las
> („eine unbrauchbare Adresse heißt nicht erreichbar, nicht Absturz"), hielt die
> Sache für erledigt; drei Zeilen weiter galt sie nicht.
>
> **Und dieselbe Lücke lag in einer zweiten Datei.** ComfyUI ist der zweite
> Dienst, dessen Adresse jemand von Hand einträgt: `mesh.reachable` fing nur
> `OSError`, `mesh.fetch` nur `HTTPError` und `URLError`. Die Familien stehen
> jetzt in `discover.py` — `BROKEN_ADDRESS` für „das ist keine Adresse",
> `UNUSABLE_ADDRESS` für „keine Adresse oder niemand hört zu". Zwei Namen, weil
> zwei Lagen zwei Handlungen brauchen.
>
> **Die dritte Ebene ist die, die den Fall gar nicht erst entstehen lässt.** Auf
> Roberts Ansage („genug Infos für Neunutzer, damit sie es sicher ausführen
> können"): Der Einrichtungsdialog fragte „Adresse, unter der es erreichbar
> ist:" und speicherte, was kam. Er nennt jetzt ein Beispiel aus dem Werkzeug
> selbst (`ExternalTool.url`, damit es mit der Vorgabe altert), sagt warum kein
> Pfad hineingehört, und prüft die Eingabe über `discover.unusable_address` —
> wer einen Ordner einträgt, bekommt dasselbe Feld noch einmal, mit dem Grund
> darüber und seiner Eingabe darin.
>
> **Was daraus als Regel bleibt:** Wer eine Ausnahme an der Stelle fängt, an der
> sie aufgetreten ist, hat die Frage „welche zweite Stelle hat dasselbe Muster?"
> noch nicht gestellt. Beide Runden sind an genau dieser Frage gescheitert,
> einmal je Ebene.

**Der Satz, der bleibt: Was ein Werkzeug über sich selbst sagt, tippt der Kunde
ein.** `http://127.0.0.1:11434` ist die Adresse, die Ollama in seiner eigenen
Ausgabe nennt — sie ist die wahrscheinlichste Eingabe und nicht die
unwahrscheinlichste. Ein Feld, das nur die volle Chat-URL verträgt, ohne das zu
sagen, ist gegen den Regelfall gebaut.

- [x] **Ein Schlüssel, der nicht gilt, sperrt das lokale Modell aus.**
      `backends()` (`llm.py:1022`) gibt `(AnthropicBackend(), OllamaBackend())`,
      `first_available()` nimmt den ersten mit `available` — und bei Anthropic
      heißt das `keys.read(self.id) is not None` (`llm.py:331`), also **ob ein
      Schlüssel da ist, nicht ob er gilt**. Ein einziger Tippversuch sperrt ein
      vollständig eingerichtetes Ollama dauerhaft aus, und nichts sagt es.

      **Verhaltensänderung, deshalb eine Entscheidung von Robert.** Vorschlag:
      Nach einem `authentication_error` gilt das Backend für diese Sitzung als
      nicht verfügbar, der Chat fällt auf das nächste zurück und sagt in einem
      Satz, dass er es getan hat. Die Alternative — beim Speichern einmal gegen
      den Anbieter prüfen — kostet einen Netzaufruf im Einstellungsdialog und
      widerspricht dem Grundsatz, dass ohne Netz alles außer dem Chat geht.

- [x] **Die Adresse, die Ollama selbst nennt, zerlegt drei Aufrufe.**
      `installed_models` (`llm.py:731`) und `pull_model` (`llm.py:759`) bauen
      ihre Adresse mit `.replace("/api/chat", "/api/tags")` beziehungsweise
      `"/api/pull"` aus der eingetragenen URL. Enthält die kein `/api/chat`,
      greift das Replace nicht — die Anfrage geht an die Wurzel, und dasselbe
      gilt für den Chat-Aufruf selbst.

      **Gemessen gegen ein echtes Ollama**, nicht vermutet: POST auf die Wurzel
      **405**, POST auf `/api/pull` **200**, GET auf die Wurzel **200**. Die 405
      im Kundenprotokoll sind damit erklärt.

      Der Fix ist eine Normalisierung statt einer Ersetzung: Basis-URL erkennen,
      Pfad anhängen; eine eingetragene volle URL weiter akzeptieren. Dazu ein
      Test mit beiden Schreibweisen — der heutige Bestand prüft nur die volle.

- [x] **Ein Pfad im Adressfeld reißt den Einrichtungsdialog ab.**
      `discover.reachable` (`discover.py:437`) fängt `OSError`, aber
      `urlparse("http://C:\\Users\\…").port` wirft `ValueError`. Der Arbeiter
      des Installationsdialogs stirbt mitten im Einrichten
      (`install_dialog.py:84` → `install.py:426` → `tools.py:74`). Eine Zeile
      am `except`, und daneben die Frage, warum dasselbe Feld bei OpenSCAD
      einen Pfad und bei Ollama eine Adresse meint, ohne es zu sagen.

- [x] **Das Schlüsselfeld nimmt eine kopierte Fehlermeldung an.**
      `keys.store` (`keys.py:62`) legt jeden String im Schlüsselbund ab — auch
      einen mehrzeiligen, der aus einer Fehlermeldung samt Knopfbeschriftung
      besteht. Beim nächsten Zug landet er als `x-api-key` in einem HTTP-Header
      und fliegt als `ValueError` aus `http.client.putheader`. **Regel 17:** Der
      Kunde liest „Im Programm ist ein unerwarteter Fehler aufgetreten" und
      wird um einen Fehlerbericht gebeten — für einen Tippfehler.

      Prüfung beim Speichern: trimmen, Zeilenumbrüche und Nicht-ASCII ablehnen,
      und die Ablehnung als Satz mit Vorschlag zurückgeben.

- [x] **„Das Sprachmodell hat nicht geantwortet" sagt nicht, welches.**
      Der Kunde richtete Ollama ein und las diesen Satz über einem
      Anthropic-Schlüsselfehler. Geantwortet **hatte** das Modell — nur ein
      anderes als das, das er gerade eingerichtet hatte. Die Meldung nennt den
      Anbieter nicht, und genau das hätte den Fall in Minute zwei beendet statt
      in Stunde drei.

---

## Der Anwendungsstart misst 2100 ms gegen eine Marke von 1233 (24.08.2026)

`test_performance.py::test_the_application_is_usable_quickly` ist rot:
**2087 ms gegen eine Bestmarke von 1233 ms**, und `tests/.performance.json`
zählt neun Überschreitungen in Folge bei einer Schwelle von zwei. Gemeldet von
3d-druck-43 mit dem Verdacht auf `72e7bd2`.

**Der Verdacht hält nicht.** Gemessen im Wechsel, damit die Maschinenlast für
beide Stände dieselbe ist — je ein eigener Prozess mit dem Treiber des Tests,
„ohne" ist ein Arbeitsbaum auf `9862b57`, also vor `acb0dd5`, `e0540a1` und
`72e7bd2`:

    Runde 1:  mit 2147 ms   |   ohne 2112 ms
    Runde 2:  mit 2130 ms   |   ohne 2094 ms
    Runde 3:  mit 2094 ms   |   ohne 2131 ms

Der Unterschied liegt im Rauschen, in Runde 3 ist der alte Stand sogar
langsamer. `72e7bd2` kam ohnehin nicht in Frage: Er ändert Regeldokumente und
in `parts/user.py` genau zwei Docstrings.

**Was die Zahl streuen lässt, sagt der Test selbst.** Sein Docstring nennt für
denselben Tag 13 764 ms kalt und 2500 bis 3000 ms warm, und die Marke ist der
**kleinste** je gemessene Wert. Am 24.08.2026 arbeiteten vier Sitzungen
gleichzeitig auf dieser Maschine.

- [x] **Marke neu setzen oder Ursache suchen — und zwar allein auf der
  Maschine.** Die Bestmarke von 1233 ms stammt aus einer Phase, die sich heute
  nicht wiederherstellen lässt, solange mehrere Sitzungen messen. Wer das
  entscheidet, fährt die Marke zuerst bei null fremden Prozessen: Liegt sie
  dann wieder bei 1233, ist der Wert gut und die Roten sind Fremdlast; liegt
  sie bei 2100, ist die Marke von einem Glückstreffer und gehört korrigiert.
  **Zurückgesetzt wurde sie bewusst nicht** — eine Marke, die man beim ersten
  roten Lauf hochsetzt, misst nie wieder etwas.

  **Entschieden und ausgeführt.** Robert am 25.08.2026: „ursachen suchen,
  optimieren und falls nötig marke anheben." Gesucht (3d-druck-43,
  26.08.2026, unter dem Prüfschloss): Best-of-6 sind 2206 ms, und
  `-X importtime` legt die Verteilung offen — der Importblock
  `trimesh`/`scipy`/`networkx` kostet ~1,9 s der 2,2 und hängt am Füllen
  des Registers (`load_operations` → `geom.mesh`); VTK lädt längst
  verzögert, `main_window` kostet 128 ms, die Rezepte tauchen nicht auf.
  Der Code bleibt doppelt ausgeschlossen (Commit-Wechsel oben, Importbild).
  Also angehoben: Marke 2206 ms, Zähler genullt (`tests/.performance.json`,
  maschinenlokal). Der Hebel für eine echte Senkung — Geometrieimporte aus
  `load_operations` in die erste Auswertung verschieben — wäre ein eigener
  Umbau über alle Op-Module; er steht hier benannt und ist nicht Teil
  dieses Punktes.

---

## Die dünnste Gruppe des Katalogs ist die meistgefragte (24.08.2026)

Auf Roberts Frage nach dem, was im Katalog fehlt und oft gefragt ist,
abgeglichen: Bestand, Downloadkategorien der Modellportale, und die Frage, ob
es überhaupt ein **Baustein** ist. Die Liste steht in
`konzepte/konzept-befestigungssysteme-2026-08.md` Teil III.

**Der Katalog ist nicht unvollständig, er ist ungleich.** Alle dreizehn der
Erstbestückung aus §24.1 stehen, es sind achtzehn geworden — aber:
Verbindungen 4, Mechanik 5, Befestigung 3, Struktur 2, Kalibrierung 3, und
**Kabel und Schläuche: einer.** Kabelmanagement ist die meistgenannte
Kategorie der Portale, und was wir dafür haben, ist ein *Loch* (Durchführung),
kein *Halter*.

**Der erste ist gebaut** (`4b9bef2`, 24.08.2026): Der Kabelclip steht in der
Gruppe, die vorher nur ein Loch hatte. Ein liegender C-Bügel auf einem Sockel,
Maße aus der Schlauchtabelle, die Öffnung enger als das Kabel. Was dabei über
den Baustein hinaus anfiel, steht im Docstring seines Tests: `trimesh.contains`
braucht `rtree` und fällt seit heute aus, und eine Schnittmenge gegen ein
Nennmaß-Kabel misst die Rückfallkette statt der Passung — für vier Größen
8,6 · 10,4 · 9,3 · 9,4 mm³, absolut konstant statt proportional.

**Und einer der fünf war keiner.** Der Schwalbenschwanz ist am 25.08.2026
gestrichen: `shapes.dovetail` gibt es, und zwar als Form des Passstifts
(`dowel`) und als eine der vier Verbinderformen beim Teilen. Gesucht worden
war nach einem Baustein *dieses Namens*; er ist keiner, sondern ein
Parameterwert an zwei Stellen. **Eine Lücke im Katalog ist erst eine, wenn man
nach der Sache gesucht hat und nicht nach dem Namen.**

- [x] **Die Liste ist abgearbeitet** (25.08.2026). Von fünf Vorschlägen sind
  vier gebaut und einer gestrichen:

      Kabelclip        4b9bef2   die dünnste Gruppe hatte nur ein Loch
      Eckwinkel        327319b   die Rippe hält eine Wand, nicht die Ecke
      Standfuß         9a900df   Fuß oder Tasche, subtractive_on wie beim Stift
      Scharnierauge    —         das Filmscharnier biegt, dieses dreht
      Schwalbenschwanz gestrichen — den gibt es als Form des Passstifts

  Der Katalog zählt damit zwanzig Bausteine statt der dreizehn aus der
  Erstbestückung, und keine Gruppe steht mehr mit einem einzigen Eintrag da.

  **Vom Bolzenscharnier ist die Hälfte geworden, und die andere Hälfte ist
  eine Frage** — sie steht unter „Ein Baustein muss ein Körper sein, ein
  Gelenk sind zwei".

  **Was ausdrücklich nicht dazugehört:** Griffe, Knöpfe, Batteriedeckel,
  Möbelfüße als fertige Teile. Sie sind oft gefragt und sind **Modelle, keine
  Bausteine** — sie werden nicht an ein Teil gesetzt, sie *sind* das Teil. Der
  Katalog ergänzt Modelle, er ersetzt sie nicht.

---

## Ein Baustein muss ein Körper sein, ein Gelenk sind zwei (25.08.2026)

Beim letzten Baustein der Katalogliste — dem Bolzenscharnier — stieß die Sache
an eine Regel, und die Regel steht nicht dort, wo man sie sucht.

**Ein Scharnier, das schon beim Drucken beweglich ist, besteht aus zwei
Teilen.** Der Bereichstest verlangt aber `component_count == 1` („falls
apart"). Beide Forderungen zusammen gehen nicht.

**Und die Einteiligkeit steht nicht im Bauplan.** §24.3 nennt vier Dinge:
wasserdicht, Mindestwandstärke, keine Selbstdurchdringung an den Grenzen,
Merkmale korrekt benannt. Die Einteiligkeit hat der Test hinzugefügt, und zwar
aus einem guten Anlass: Die Rastnase zerfiel, weil sie die Fläche nur berührte
(§39). Gemeint war „zerfällt nicht **versehentlich**" — was der Test prüft, ist
„ist nicht mehrteilig".

**Gebaut wurde deshalb das Scharnierauge** (`hinge_eye`): eine Lasche mit
Bohrung, einteilig, und zwei davon plus ein Passstift ergeben ein Gelenk. Das
ist im Rahmen und nützlich, und es beantwortet die Frage nicht.

- [x] **Soll die Bibliothek erklärt mehrteilige Bausteine kennen?** Dahinter
  steht eine ganze Klasse: Scharniere, Ketten, Kugelgelenke, Schnappdeckel mit
  Achse — print-in-place-Mechanik ist einer der Gründe, aus denen Leute
  drucken. Dagegen steht, dass ein Baustein **angebaut** wird: Was am Träger
  hängt, hängt an ihm, und ein Teil, das lose danebenliegt, ist eher ein Modell
  als ein Baustein.

  Wer es entscheidet, ändert §24.3 und den Test dazu — beides mit Ansage. Ein
  Mittelweg wäre eine Deklaration am Baustein (`parts=2` statt einer stillen
  Ausnahme), damit der Test weiter fängt, was **versehentlich** zerfällt.

  **Entschieden am 25.08.2026 (Robert, auf Vorlage von 3d-druck-46): Ja, und
  zwar als Deklaration** — genau der Mittelweg. §24.3 trägt die Ausnahme seit
  demselben Tag: mehrere Körper erlaubt, wenn der Baustein ihre Zahl
  deklariert; geprüft werden dann die Druckspalten gegen das Materialprofil
  und die gebaute Zahl gegen die Deklaration, und unerklärtes Zerfallen
  bleibt rot.

- [x] **Die Deklaration bauen** — am 27.08.2026 in vier Schritten, alle vier
  gemessen und mit Gegenprobe:

  `bodies` am `register_part` (`93fd3783`) sagt, wie viele Körper ein Baustein
  **erklärt** hervorbringt. Der Bereichstest prüft die gebaute Zahl gegen die
  erklärte, die Suite ebenfalls: Wer nichts deklariert, hat `bodies=1` und
  damit wortgleich die alte Zusage; unerklärtes Zerfallen bleibt rot. Das ist
  der Unterschied zu einer Ausnahme im Test — die Prüfung wird nicht
  schwächer, sondern genauer.

  Das Bolzenscharnier (`6d3ac074`) ist der erste Nutzer und der Beleg, dass es
  trägt: zwei Laschen um einen mitgedruckten Bolzen, wasserdicht bei jedem
  Spaltmaß. Es ist das Scharnier, das `hinge_eye` am 25.08. nicht sein durfte.

  Die Druckspaltenprüfung (`ff8f7332`) misst den engsten Abstand zwischen den
  Teilen gegen das kalibrierte Material. **Dabei kam ein zweiter Fund heraus,
  der größer ist als der erste:** Der Bereichstest fuhr `play = 0` und prüfte
  damit eine Geometrie, die im Einsatz nie entsteht — `insert_part` setzt dort
  seit je den Profilwert ein. Beim Scharnier war das ein Gelenk mit einer
  Hundertstel Spalt, das beim Drucken verschweißt.

  Und eine Toleranzfrage, die kein Detail war: Der Vergleich läuft gegen
  `EPS_DISPLAY` und nicht gegen `EPS_GEOM`. Ein facettierter Zylinder zeigt
  seine Sehne und nicht den Bogen, der gemessene Spalt fällt also um
  Bruchteile kleiner aus — mit dem Rechenepsilon meldete die Prüfung ein
  Scharnier, das genau richtig gebaut war.


## Das Kontextmenü wuchs um eine Zeile, und die Prüfung sah woanders hin (25.08.2026)

Ein Review von 3d-druck-61 fragte, ob die Zwölf-Zeilen-Grenze für das
zusammengesetzte Kontextmenü überhaupt gemessen wird. Sie wird es nicht — und
beim Nachrechnen kam heraus, dass auch die vorhandene Prüfung längst an anderen
Zahlen rechnete als der Katalog.

**`test_a_group_of_one_never_becomes_a_submenu` prüft `folded_groups`
gründlich**, aber mit einer von Hand eingetragenen Verteilung: Bausteine 10,
Ändern 5, Erzeugen 2, Vorbereiten 2, macht 19 Operationen. Die stimmte am
24.08.2026. Einen Tag später standen an einer Fläche **31**, davon 22
Bausteine. Die Formel stimmte weiter; die Zahlen, an denen sie geprüft wurde,
waren keine Aussage über das Produkt mehr. Das ist dieselbe Art alternder
Liste, die in `test_parts.py` schon zweimal zugeschlagen hat, und sie fällt
nicht auf, weil ein Test mit ausgedachten Zahlen genauso grün aussieht wie
einer mit echten.

**Gemessen ergibt das Flächenmenü 13 Zeilen.** Zehn Operationszeilen (fünf
„Ändern", zwei „Erzeugen", zwei „Vorbereiten", eine für das gefaltete
Untermenü „Bausteine") plus drei feste: Sichtbarkeit und der Skizzenschritt.
Die Grenze aus der Testart „Oberflächengrenzen" nennt zwölf.

`_menu` zählt die drei bewusst nicht mit — es ruft `folded_groups` ohne
`fixed`, und der Grund steht in seinem Docstring: Wer sie mitzählte, müsste
eine zweite Gruppe falten, und die nächste wäre „Ändern", mit der Bohrung
darin. Genau der Eintrag also, dessen zweiter Klick den ganzen Umbau vom
24.08.2026 ausgelöst hat.

Seit `5ac89d32` rechnet der Test aus dem Register statt aus einer Liste, prüft
die Gegenrichtung mit (jede gefaltete Gruppe wieder aufgemacht muss die Grenze
sprengen — sonst war ihre Faltung ein Klick ohne Not) und lässt **genau eine**
Zeile über der Grenze zu.

- [x] **Die Ausnahme ist aufgelöst — und keine der beiden erwarteten Antworten
  war es.** Entschieden am 25.08.2026 (3d-druck-46 unter Roberts
  Bedienungsvollmacht, umgesetzt von 3d-druck-ce): **zweite Gruppe falten,
  Ausnahme nicht bestätigen.** Die Wahl fiel damit auf den Zweig, der die
  Testart *nicht* anfasst — der Grund, aus dem der Absatz darüber die
  Bedienungsvollmacht als nicht zuständig führte, galt allein der anderen
  Möglichkeit.

  Der Satz oben stellte die Frage aber als „13 Zeilen **oder** die Bohrung im
  Untermenü", und das war eine falsche Alternative: Sie folgte aus
  `folded_groups`, das die **größte** Gruppe zuerst faltete. Nach „Bausteine"
  fehlte genau eine Zeile, und die größte der übrigen ist „Ändern" — daher die
  Bohrung. Gefaltet wird jetzt die **hinterste Gruppe aus `MENU_GROUPS`, die
  allein genügt**; genügt keine allein, weiter die größte. Am Flächenklick
  trifft das „Vorbereiten": zwei Einträge, eine gesparte Zeile.

  Gemessen: 22 Bausteine, 5 Ändern, 2 Erzeugen, 2 Vorbereiten plus drei feste
  Zeilen — **12 von 12**, „Ändern" und „Erzeugen" stehen offen, kein Eintrag ist
  tiefer gerutscht als vorher. Am Lochklick ändert sich nichts (7 + 3 = 10, kein
  Falten). Die drei festen Zeilen zählt `_add_operations` am gebauten Menü ab
  statt als Konstante — beide Schritte darüber sind an Bedingungen geknüpft.
  Die sieben Rechenbeispiele in `test_a_group_of_one_never_becomes_a_submenu`
  ergeben unverändert dasselbe; `test_the_drill_stays_one_click_away_on_a_face`
  hält die Zusage fest, die eine Zeilenzählung nicht sieht, und ist gegen den
  zurückgestellten Fix einmal rot gesehen worden.

## Das Schlüsselloch hängt waagerecht, und sein eigener Docstring sagt es anders (25.08.2026)

Gefunden beim Beheben desselben Fehlers am Lochwand-Einhänger, der von diesem
Baustein abgeschrieben hatte.

`keyhole` schreibt in seinem Docstring: *„Der Schlitz läuft in -Y, damit er
nach dem Umlegen auf eine senkrechte Wand aufwärts zeigt: das Teil fällt, die
Schraube steht relativ dazu höher."* Der Code verschiebt den Körper auch in
−Y — aber er **baut** ihn mit `shapes.slot(breite, breite + drop, tiefe)`, und
`slot` legt seine Länge in **X**. Gemessen an `keyhole(drop=8)`: 15,58 mm in X,
7,60 mm in Y. Die 15,58 sind `head + 0,6 + drop`, also genau der Schlitz — er
liegt quer zu der Richtung, in der das Teil fällt.

Ein Schlüsselloch mit waagerechtem Schlitz hält nicht: Die Schraube wandert
seitlich statt sich zu verklemmen, und das Teil hängt nur, solange niemand
dagegenstößt.

**Warum das hier steht und nicht behoben ist:** Der Baustein gehört keiner
Sitzung, und die Änderung ist eine Maßänderung an einem ausgelieferten
Baustein (§24.4, `parts_version` und Änderungseintrag). Der Befund ist
gemessen und in zwei Zeilen nachvollziehbar; ein Prüfdruck bestätigt ihn in
Minuten.

- [x] **Den Schlitz in die Fallrichtung drehen** — `shapes.turned(…, 90.0)` wie
  jetzt beim Lochwand-Einhänger, dazu `parts_version` und ein Eintrag.

  **Weiter reicht es nicht:** Von 23 Bausteinen benutzen nur zwei
  `shapes.slot`, und der zweite ist der Lochwand-Einhänger, der seit `57d515b3`
  ausdrücklich dreht. Nachgezählt, bevor jemand suchen geht — die Falle ist
  echt (`slot` legt seine Länge immer in X, und wer das nicht weiß, verschiebt
  in Y und meint, er habe gedreht), aber sie ist hier nur einmal
  zugeschnappt.

  **Behoben mit `45f87d8e`** („Zwei Bausteine hatten ein Oben, und es zeigte
  in verschiedene Richtungen"): der Schlitz dreht mit `shapes.turned(…, 90.0)`,
  `parts_version` 4, Änderungseintrag `SLOT_RUNS_DOWNWARD`. Der Punkt stand
  hier zwei Tage länger offen als der Fix — die behebende Sitzung kannte den
  Abschnitt nicht, und das Register zog erst am 25.08.2026 nach.


## Der Haken hält, bis jemand das Teil anhebt (25.08.2026)

Robert hat angeregt, nach vorhandenen SKÅDIS-Haken zu suchen — und die Suche
liefert ein Ergebnis, das keine Maßkorrektur ist, sondern eine Grenze.

**Das Herausfallen ist das bekannte Problem des ganzen Systems**, auch bei den
Originalhaken von IKEA. Der Satz, der es am schärfsten fasst, stammt aus einer
Bauanleitung: *„any single piece will always be able to detach in the same way
it attached."* Ein Teil, das man einhängt, indem man es einführt und absinken
lässt, löst sich, indem man es anhebt und herauszieht — und genau diese Geste
macht jemand, der etwas vom Halter nimmt.

Der Lochwand-Einhänger dieser Bibliothek hat die Eigenschaft. Sie ist kein
Maßfehler und durch bessere Maße auch nicht zu beheben: Der Sinkweg, der die
Nase greifen lässt, ist derselbe Weg zurück.

**Es gibt einteilige Lösungen**, und das ist der interessante Teil. Mehrere
Entwürfe arbeiten mit einer federnden Zunge, die beim Absinken hinter der Platte
einrastet und zum Lösen eingedrückt werden muss („self locking", „snap-lock
mount"). Das bliebe **ein** Körper und verstieße nicht gegen §24.3 — die
Bibliothek hat mit Rastnase und Schnappverbindung schon zwei Bausteine, die
federnde Arme rechnen.

**Nachgesehen am 25.08.2026, wie andere es lösen** — und das Ergebnis engt die
Bauform stark ein.

Die verbreitete Mechanik ist keine Nase am Zapfen, sondern eine **Verspannung
über zwei Schlitze**: „sliding the lower hook into the pegboard, then bending
slightly the springy thin element so that the top hook can slide into the
groove above". Ein Haken trägt, ein zweiter sitzt auf einem federnden Arm, und
zwischen beiden liegt ein Rastermaß.

**Warum nicht einfacher, im Zapfen selbst?** Weil kein Platz ist, und zwar nach
den eigenen Regeln der Bibliothek. `SNAP_RATIO` verlangt zehn zu eins,
`SNAP_MIN_ARM` mindestens 0,8 mm — ein Federarm misst damit mindestens 8,0 mm.
Der Zapfen ist bei 0,25 mm Spiel **7,38 mm** hoch. Es fehlen sechs Zehntel, und
darunter wäre der Arm eine Fahne, die beim ersten Einrasten abreißt. Quer geht
es auch nicht: Der Zapfen ist so breit wie der Schlitz, eine seitlich federnde
Zunge hätte keinen Weg.

Zwischen zwei Schlitzen sind es dagegen 40 mm — reichlich für einen Arm.

- [x] **Soll der Einhänger eine Verriegelung über zwei Schlitze bekommen?** Sie
  bräuchte `upright` und mindestens zwei Haken, einen davon auf einem Federarm,
  und einen Parameter *Verriegelung* zum Abschalten für den, der das Teil oft
  abnimmt. Dagegen spricht, dass eine Feder Materialkenntnis braucht — die
  Federarme der Schnappverbindung ziehen ihre Maße aus dem Materialprofil, und
  für PETG steht dort anderes als für PLA. Dafür spricht, dass das
  Herausrutschen das bekannteste Ärgernis des Systems ist.

  Bis dahin sagt der `caveat` es dem Kunden: „Er löst sich auf demselben Weg,
  auf dem er eingehängt wird."

  **Entschieden und gebaut am 25.08.2026 (Robert: „aus Kundensicht perfekt"),
  und zwar anders als hier vermutet:** Die Zunge braucht keine zwei Schlitze.
  Die Messung, die „7,38 mm, gebraucht 8,0" ergab, suchte den Federarm in der
  **Höhe** des Zapfens — in der **Tiefe** (Plattendicke plus Nase) sind
  8,33 mm da, und dorthin läuft er. Der Einhänger trägt jetzt eine federnde
  Rastzunge über dem Zapfen (`latch`, Vorgabe an, abschaltbar): eingerastet
  hält das Teil in jeder Höhe, gelöst wird durch Niederdrücken durch den
  Schlitz. Randdehnung 1,5 % gegen die 2-%-Grenze, neun Mutationsproben,
  `parts_version` 7 und 8, caveat und Handbuch erzählen die neue Lage. Lässt
  ein fremdes Lochwandmaß keinen Federweg, hält der Baustein an und sagt es
  (Regel 21), statt einen starren Vorsprung zu bauen.

## Was das Update-Review liegen ließ (26.08.2026)

Aus den elf Durchgängen über die Commits seit 0.1.5 (Befundliste in
`.claude/.state/update-review-0.1.5-2026-08-25/BEFUNDE.md`) ist alles
Zugeteilte behoben; ein Fund entstand erst beim Schließen der Testlücken
und braucht einen Umbau statt eines Tests.

- [x] **Regel 17 endet an der Auswertungsgrenze — gemessen am 27.08.2026,
  zehn von sechzehn Fehlerklassen verlieren ihre Auswege.** Ein Fehler, der
  die Kette anhält, erreicht den Prüfbericht ohne seine spezifischen
  Handlungen: `Finding` hat kein solches Feld, und `_finding_from` in
  `scene/evaluate.py` baut es aus Code, Meldung, Objekt und Werten — die
  `suggestions` des Fehlers stehen dort nicht.

  **Was danach noch ankommt**, ist genau eine Handlung: `panels.actions_for`
  gibt jedem Befund, dessen Code mit `op.` beginnt und der eine `op_id` hat,
  pauschal `CORRECT_INPUT`. `FINDING_ACTIONS` daneben kennt 16 Codes
  namentlich, **keinen einzigen davon aus der `op.*`-Familie**.

  **Die Messung** (Klassenvorgaben `default_suggestions` in `errors.py`, nicht
  nur die einzeln mitgegebenen — die überschreiben nur):

  | Klasse | verliert |
  |---|---|
  | `NotManifoldError`, `GeometryError` | `repair_and_retry`, `show_locations` |
  | `BooleanFailedError` | `repair_and_retry`, `use_voxel_stage`, `show_locations` |
  | `OutOfBuildVolume` | `split_model`, `scale_to_fit`, `choose_printer` |
  | `AmbiguityError` | `choose` |
  | `ExternalToolError` | `install`, `retry` |
  | `FileWriteError` | `retry`, `save_elsewhere` |
  | `LicenceRequired` | `enter_licence_key`, `buy_licence` |
  | `InstallationDamaged` | `open_download_page`, `report_error` |
  | `InternalError` | `report_error`, `show_details` |

  Sechs Klassen verlieren nichts, weil ihre Vorgaben `CORRECT_INPUT`/`CANCEL`
  ohnehin nicht übersteigen: `AppError`, `UserError`, `ValidationError`,
  `NeedsSolidError`, `SketchConflictError`, `UnitUnknownError`. **Das ist die
  gute Nachricht** — die häufigste Klasse in einer Operation ist
  `ValidationError`, und die ist gedeckt.

  **Die schwerste Lücke sind die drei Geometrieklassen.** Sie verlieren
  `repair_and_retry` und `show_locations` — die zwei Handlungen, die bei einem
  kaputten Netz überhaupt weiterhelfen. Der Kunde bekommt stattdessen
  „Eingabe korrigieren", und an der Eingabe liegt es nicht.

  **Entscheidung, die noch aussteht** — und die Messung spricht für das Feld:
  Familien-Einträge in `FINDING_ACTIONS` müssten `op.<operation>.<klasse>`
  abdecken, und das sind 90 mal 16 Zeilen. Der Kommentar über
  `actions_for` nennt dieses Argument selbst („das sind 86 mal n Zeilen, die
  alle dasselbe sagen würden") — er zieht daraus nur den Schluss, pauschal
  `CORRECT_INPUT` zu geben, statt das Feld durchzureichen. Ein
  `suggestions`-Feld am `Finding` ist einmal Arbeit und trägt alle sechzehn
  Klassen; es berührt `types.Finding`, `scene/evaluate._finding_from` und
  `ui/panels.actions_for`.

  **Nachtrag vom selben Abend: Zehn ist die Obergrenze, nicht die Zahl.** Die
  Tabelle oben zählt, welche Klasse Auswege *hätte*, die über
  `CORRECT_INPUT`/`CANCEL` hinausgehen. Sie sagt nicht, ob die Klasse je in
  einer Operation fliegt — und nur dann verliert sie etwas. d1 hat es für
  `ExternalToolError` am Aufrufgraphen gemessen: `slice_model` hat genau einen
  Aufrufer, den Druckdialog, und dort landet der Fehler im Fehlerdialog, wo
  seine Auswege ankommen. Diese Klasse ist nicht betroffen.

  Für die übrigen neun habe ich zwei Näherungen gemessen, und **beide sind die
  falsche Frage**:

  | Frage | Antwort |
  |---|---|
  | Wird die Klasse in einer Datei mit `@register_op` geworfen? | **3** von 10 (`GeometryError`, `InternalError`, `NotManifoldError`) |
  | Ist die werfende Datei aus einer Operationsdatei über Importe erreichbar? | **9** von 10 (nur `OutOfBuildVolume` wird nirgends geworfen) |

  Die erste ist zu eng: `geom/boolean.py` trägt kein `@register_op` und wirft
  `BooleanFailedError` aus jeder Booleschen Operation heraus. Die zweite ist
  zu weit: `export/handover.py` ist über Importe erreichbar, wird aber nur aus
  dem Dialog gerufen. **Die Wahrheit liegt zwischen drei und neun, und für
  jede einzelne Klasse entscheidet die Aufrufkette, nicht der Importgraph.**

  Wer den Fix baut, braucht diese Aufteilung nicht: Ein `suggestions`-Feld am
  `Finding` trägt alle Fälle, ohne dass jemand sie zählt. Wer dagegen
  Familien-Einträge in `FINDING_ACTIONS` ergänzen will, muss genau wissen,
  welche Kombination vorkommt — und das ist der zweite Grund gegen diesen Weg.

  Gefunden beim Testlücken-Schließen am 26.08.2026, belegt an
  `scene/ops.py:361`.

  **Behoben am 29.08.2026, an der Grenze statt je Fehlerfamilie.** `Finding`
  trägt nun dieselben `suggestions` wie die abgefangene `AppError`; die
  Auswertung reicht sie unverändert durch, und der Prüfbericht zieht sie jeder
  pauschalen Zuordnung vor. Damit bekommt ein Geometriefehler *Reparieren und
  erneut versuchen* sowie *Stellen zeigen*, während ein ungültiger Zahlenwert
  weiter gezielt seinen Schrittdialog öffnet.

  Der zweite halbe Fehler lag im Plattencache und in `report.json`: Ohne
  Serialisierung wäre der Ausweg nach einem warmen Cache oder nach erneutem
  Öffnen wieder verschwunden. Format 15 → 16 markiert deshalb die neue
  Zusage; eine ältere Datei bleibt ohne erfundene Handlungen gültig und wird
  beim Rechnen neu befüllt. Drei Anschlussprüfungen decken Auswertung,
  Datenrunde und Oberfläche getrennt, die letzte den konkreten
  Geometriefehler statt nur ein künstliches Feld.

## Was der Gesamtreview liegen ließ (25.08.2026)

Sechs Pakete des Gesamtreviews vom 25.08.2026 sind auf main (Geometrie,
Schicht, Import/Export, Agent, Querschnitt, Website); die Zuordnungsfrage
aus §21.3 gilt seither nur noch Merkmalen, auf die eine Passung oder
Operation verweist. Vier Dinge sind bewusst liegen geblieben:

- [x] **Die stehende Wand weicht unter 0,9 mm weiter ab.** Das Raster des
  Aushöhlens hält das Versprechen ±1/6 mit `MIN_PITCH = 0,3` dort nicht
  (gemessen: 30 % bei 0,5 mm Wand); ein feineres Raster ist eine
  Speicherentscheidung gegen `MAX_GRID_STEPS`. Bis dahin nennt der Befund
  `eroded_mm` und `tolerance_mm`, und `hollow.coarse_grid` warnt.

  **Entschieden am 26.08.2026, mit Messreihe: kein feineres Raster.** Schon
  die eine Stufe feiner (Wand/3 statt `MIN_PITCH`) kostet am kleinsten
  nützlichen Körper +325 MB und das 3,4-fache an Zeit, am realistischen
  100-mm-Teil +898 MB und das 4,2-fache — an einer Operation am Knopf. Die
  Grenze liegt strukturell bei 3 × `MIN_PITCH` = 0,9 mm und wird ehrlich
  ausgewiesen. Nebenbefund der Messung: `MAX_GRID_STEPS` ist gar nicht die
  Gegenpartei — `hollow` ruft `solid_field` mit eigener Weite, die Bremse
  ist allein `MIN_PITCH`. Gemessen auch ein Weg, der den Rundungsterm
  streicht (Abstandsfeld statt iterierter Erosion, +0,16–0,69 s, 0 MB,
  konstanter −pitch/2-Versatz zum Kalibrieren) — notiert, nicht umgesetzt.
  **Was den Punkt schließt:** die Messzahlen in den Docstring von
  `erosion_steps` und `fair_wall_mm = 3 * MIN_PITCH` in die `values` von
  `hollow.coarse_grid` — zwei Zeilen in `hollow.py`, das im geom-Paket von
  3d-druck-46 liegt; die Zahlen sind ihr übergeben.

  **Geschlossen am 26.08.2026:** Die zwei Zeilen sind mit `8f355bdb`
  gelandet — die Messreihe steht am `erosion_steps`-Docstring, und
  `fair_wall_mm` nennt die Grenze als Wert im Befund.

- [x] **Drei Messwerkzeuge des Kerns haben keinen Anschluss — geschlossen am
  28.08.2026.**
  `angle_between`, `bounding_box_of` und `volume_of` (§18.3) existieren,
  getestet, und sind jetzt angeschlossen: Die Messleiste misst den Winkel
  zwischen zwei erkannten ebenen Flächen und zeigt Grad statt einer Länge.
  Die Statusleiste berechnet Hüllmaß und Gesamtvolumen aus der vollständigen
  Ein- oder Mehrfachauswahl. Ein untauglicher Winkelklick bleibt nicht stumm,
  sondern sagt, dass zwei erkannte ebene Flächen nötig sind.

- [ ] **Die orient_200-Marke fällt auf jeder Maschine einmal.** Die
  Säulenrechnung des Stützvolumens ist bewusst teurer (+23 % auf ruhiger
  Maschine, Zielwert §31 hält); die alte Zahl war 380-fach falsch. Wer den
  Leistungslauf rot sieht, setzt die Marke in `tests/.performance.json`
  neu, statt die Rechnung zurückzudrehen.

- [ ] **Das Schemabild des Skizzeneditors zeigt weniger, als der Editor kann
  — und die Frage ist, ob es das soll.** Am 27.08.2026 gegen den echten
  Editor gemessen; das Ziel steht still, seit dem 26.08. ist an
  `sketch_editor.py` nichts mehr geändert worden und die Sitzung, die umbaute,
  ist weg.

  **Ein echter Fehler war dabei und ist behoben** (23dbae7c): Der Kommentar
  über der Werkzeugzeile rechnete mit „sechs von acht Werkzeugen" und nannte
  zwei, die im Text statt im Bild stehen. Übergangen war ausgerechnet der
  Punkt — er fehlt im Bild **und** fehlte in der Aufzählung dessen, was fehlt.
  Im Handbuchtext daneben steht er mit seiner Taste, der Kunde erfährt also
  von ihm.

  **Was bleibt, ist eine Ermessensfrage und kein Fehler.** Gemessen zeigt das
  Bild vier der sieben Zeichenwerkzeuge plus zwei Sammelknöpfe, und fünf der
  zehn Bedingungsarten aus `sketch/solver._CONSTRAINT_TARGETS` (nicht:
  senkrecht, parallel, symmetrisch, fest, Referenz). Für ein Schema ist beides
  vertretbar — es soll zeigen, *wo* die Dinge liegen, nicht *welche* es gibt,
  und die vollständigen Listen stehen im Handbuchtext daneben.

  Die eine Stelle, an der das Bild wirklich hinter dem Editor liegt, ist die
  **Ebenenzeile**: Sie nennt „Draufsicht (XY) — liegend", und der Editor kann
  inzwischen auf einer Fläche des Modells zeichnen. Das ist die Stelle, an der
  eine Flächenebene erschiene. Ob das Schema sie zeigen soll, ist eine
  Entscheidung über das Bild und keine Nachpflege — deshalb steht der Punkt
  weiter offen, aber mit einer Frage statt einer Vermutung.

- [ ] **Rezepte rechnen ihren Hash bei jedem Start neu.** Die Fassung eines
  Rezepts ist der Hash über die kanonischen Daten (§24.4), und der entsteht
  beim Laden des Katalogs jedes Mal neu, statt im Dateikopf zu stehen und
  nur geprüft zu werden. Bei einer Handvoll Rezepte unmessbar; wer die rote
  Startmarke (§31) angeht, nimmt diesen Posten mit.

- [x] **Kleinreste ohne Dringlichkeit.** Das seit je unbenutzte `height` in
  `primitive_ops._object` ist am 28.08.2026 entfernt; der Aufrufervertrag
  trägt nur noch Name und Netz.

  **Die drei `ctx.profile is None`-Zweige, die hier standen, sind geprüft und
  richtig** (27.08.2026) — sie bleiben, und zwar mit zwei verschiedenen
  Fehlerklassen, was Absicht ist:

  - `create_lid` und `screw_lid` werfen einen `ValidationError` mit
    übersetztem Hinweis („Ohne Profil muss das Spiel angegeben werden"). Das
    ist richtig, weil es einen Parameter gibt, den der Nutzer setzen kann:
    `clearance` wird nur dann aus dem Profil geholt, wenn er leer ist.
  - `compensate_first_layer` wirft einen `InternalError` mit englischer Notiz.
    Auch das ist richtig, und zwar aus dem umgekehrten Grund: Das Profil geht
    an `for_object(...)` und wird **immer** gebraucht, nicht nur ersatzweise.
    Ein gesetzter `amount` hilft nicht. Der Zustand kann im Produkt nicht
    eintreten — `scene.evaluate` verlangt `profile: Profile` ohne `None`, und
    weder Oberfläche noch Kommandozeile rufen anders. Er entsteht nur im
    Testharness (`tests/test_sketch_ops.py` baut den `OpContext` mit
    `profile=None`), und für „das hätte nicht passieren dürfen" ist
    `InternalError` die vorgesehene Klasse.

  Der Anlass, das nachzumessen, war 27s Fund am selben Tag: `shell_exact`
  bekam über denselben Harness ein `profile=None` und stolperte darüber. Die
  Frage „darf ein Kontext ohne Profil überhaupt vorkommen" hat dort eine
  andere Antwort als hier, und der Unterschied ist, ob die Operation das
  Profil **ersatzweise** liest oder **immer** braucht.


## Ein Beispielprojekt, das zweieinhalb Minuten lud (26.08.2026)

Vor der Auslieferung von 0.2.0 wurden alle neun Beispiele im echten Fenster
geöffnet und die Zeit bis zur fertigen Auswertung gemessen. Sieben lagen unter
fünfzehn Sekunden. `weg3-generiert-aufbereiten` brauchte **145 Sekunden**,
viermal reproduziert, auch ohne Fremdlast — und `weg4-figur-formen` 56.

Der Befund ist behoben: Die Erkennung offener Kanten urteilte über die
**gespeicherte** Topologie statt über die geometrische. Eine STL schreibt jedes
Dreieck mit eigenen Ecken, also hat topologisch jede Kante keinen Partner —
auch an einem rundum dichten Teil. Aus 3372 Dreiecken wurden 3372
`edge_loop`-Merkmale, und die Zuordnung baute daraus eine 3372×3372-Matrix.
Gemessen: **102,3 s vorher, 0,20 s nachher**, und die Zahl im Prüfbericht ging
von 3372 auf die wahren **6**. Dieselbe Datei verschweißt geladen liefert jetzt
dieselben 6 — vorher hing die Auskunft über das Teil davon ab, in welchem
Format es ankam.

Offen bleibt daraus:

- [x] **`match()` rechnet die quadratische Zuordnung vektorisiert.** Die zwei
      Python-Schleifen über N² sind weg: Die Kosten entstehen blockweise in
      NumPy, die Rivalenmaske gemeinsam für alle zugeordneten Zeilen. Gemessen
      auf derselben Maschine: 100 Merkmale 0,098 → 0,002 s · 400 1,561 →
      0,017 s · 800 6,386 → 0,068 s · 3372 101,1 → **1,113 s**. Die Ordnung
      bleibt quadratisch, der Speicher bleibt durch 256-Zeilen-Blöcke begrenzt.
      `cost()` steht weiter als lesbare Einzelpaar-Referenz; ein Test vergleicht
      jede Matrixkomponente dagegen, einschließlich richtungsloser Achsen,
      gerichteter Normalen und `KIND_PENALTY`. `match_800` hält die Laufzeit im
      Leistungsbestand fest.
- [x] **Erledigt durch Nachmessung mit neuem Prüfstand** (72,
      `e2102440`, 30.08.2026): `tools/window_bench.py` öffnet ein
      Beispiel im echten, maximierten Fenster und zerlegt die Wartezeit
      in Posten. Gemessen: weg4-figur-formen **6,1 s** (gegen 56 am
      26.08.), weg3-generiert-aufbereiten 5,8 s (gegen 145), Dose 4,4 s
      (gegen 13) — die vektorisierte Zuordnung und die Folgearbeiten
      haben den Oberflächenanteil mitgenommen; die alte Aufteilung war
      eine Messung vor diesen Umbauten. Kontrollmessung mit 8-s-Schwelle:
      identische Zähler. Der vierte Punkt des Tages, der durchs Messen
      fällt. Ursprünglicher Wortlaut:

      **`weg4-figur-formen` kostet 56 Sekunden, und keine davon liegt im
      Kern.** Über `Session.open_project` offscreen gemessen sind es **0,82 s**;
      der Rest liegt in der Oberfläche (VTK, Aktoraufbau) und ist offscreen
      nicht messbar — siehe „Offscreen prüft nichts, was am Aktor hängt". Das
      braucht einen Prüfstand im echten Fenster, nicht eine weitere Kernmessung.
      Dasselbe gilt für rund 40 der 145 Sekunden von weg3 und 13 von
      `dose-mit-deckel`.
- [x] **Alle anderen `detect_*` sind bei ungeschweißter Topologie blind.** Roh
      geladen lieferte `detect` **null** Merkmale statt 10 (`plate_holes`), 9
      (`post_with_fillet`), 1 (`torus_ring`). Behoben am 27.08.2026 (`40bec613`):
      `detect` führt die Ecken einmal rechnerisch zusammen, bevor irgendwer
      sucht — dieselbe Toleranz wie `repair.merge_vertices`, das Netz im
      Dokument bleibt unangetastet, die Dreiecke behalten ihren Platz. Der Test
      prüft auf **Gleichheit beider Wege** statt auf feste Zahlen.
- [x] **`component_count` zählt jedes Dreieck als Komponente** — 796 statt 1.
      Behoben am 27.08.2026 (`c54a685a`): gezählt wird über die **Vereinigung**
      beider Lesarten, gespeicherte Nummern *und* Ort. Über den Ort allein
      zerfiel ein Blend-Körper mit Radius 12 in fünf Stücke — zwei Ecken 88 nm
      auseinander, ein entartetes Dreieck, und der Graph reißt an einer Stelle,
      an der nichts fehlt. Zusammenführen darf hinzufügen, nie wegnehmen.
      `fully_stitched` schneidet die Frage ab, wo jede Kante schon ihren
      Partner hat: ohne sie kostete die Erkennung 28 Prozent mehr für eine
      Antwort, die schon dastand.

## Zwei Torläufe an einem Tag, beide an derselben Stelle (26.08.2026)

`tests/test_ui.py` endet mit einer Zugriffsverletzung, sobald die Testreihenfolge
zufällig ist. Mit `-p no:randomly` laufen alle 303 Tests durch (Exit 0), ohne
den Schalter bricht es bei 23 % ab — beide Male in `panels.py` unter
`_show_scene`, einmal in `show_result`, einmal in `show_document`.

**Keine Regression:** Der Grundlagenlauf vor allen Änderungen des Tages zeigte
denselben Abbruch an derselben Stelle. Der Fall gehört zu den Signaturen A–C
weiter oben.

Im selben Tor stand `test_analysis_ui.py` **19 Minuten** still, nachdem es „135
passed in 141,65 s" gemeldet hatte — null Protokollzuwachs, 0,015 CPU-Sekunden.
Er löste sich von selbst, bevor er beendet werden konnte. Das ist Signatur C,
und die Zahl ist der Grund, warum sie hier steht: Ein Lauf, der zwanzig Minuten
länger dauert als der davor, hat wahrscheinlich gestanden und nicht langsamer
gerechnet — wer Läufe vergleicht, misst die Wanduhr mit.

**Sechste Beobachtung, dieselbe Sitzung, wenige Stunden später:** Diesmal
`tests/test_ui.py`, Exit 139 nach vier Tests — und die Stelle ist eine **neue**:
`session.py:119` im Konstruktor unter `evaluate_async` ← `apply` ←
`import_payload` ← `import_model`, ausgelöst aus `_with_two_objects`
(`test_ui.py:1150`). Derselbe Helfer wie in der vierten Beobachtung, aber nicht
`panels.py` und nicht `op_dialog.py`. Drei Wiederholungen unmittelbar danach:
**307 passed, Exit 0**, dreimal; dazu zwei grüne Läufe derselben Datei früher am
selben Tag. Fünf von sechs grün. Die Liste der Stellen ist damit auf drei
gewachsen (`panels.py`, `op_dialog.py`, `session.py`) und der Helfer auf zwei
Beobachtungen — **das ist die brauchbarere Spur als der Ort**: Was sich
wiederholt, ist nicht die Zeile, sondern der Test, der zwei Modelle einliest.

**Fünfte Beobachtung am 27.08.2026 (Skizzenmodus-Sitzung):** Diesmal traf es
allein `tests/test_operation_ui.py`, im geteilten Lauf unter dem Schloss, mit
Exit 139 — Zugriffsverletzung **während** eines Tests und nicht beim Abbau
(`test_the_caveat_reaches_every_surface_that_offers_the_operation`, Stapel über
`op_dialog.py:197`, den QCompleter der fx-Hilfe). Dieselbe Zeile, die die
dritte Beobachtung schon nannte. Sieben Wiederholungen derselben Datei, vier
mit zufälliger und drei mit der Reihenfolge des Skripts (`-m "not
performance"`): **sieben von sieben grün**, je 67 passed. Die Änderungen der
Sitzung berühren `op_dialog.py` nicht, und der Importsatz dieses Prozesses ist
unverändert — `app.ui.main_window` zieht `viewport` und `sketch_editor` seit je
gemeinsam herein, die neue Importkante zwischen den beiden fügt dort kein Modul
hinzu. Das ist keine Zuschreibung an die Familie, sondern die Gegenprobe: Die
Signatur stand hier schon, bevor die Sitzung anfing.

- [ ] **Eine Entscheidung, ob die Suite die Reihenfolge für diese Datei
      festnagelt** (`-p no:randomly` je Datei) **oder die Ursache weiter
      verfolgt wird.** Das Festnageln verdeckt einen echten Fehler; ihn zu
      verfolgen kostet die Lebensdaueruntersuchung, die im Register unter
      „Signatur C" steht.

## OpenSCAD ist ausgebaut (26.08.2026)

Robert: „brauchen wir OpenSCAD überhaupt, machen wir das nicht über unsere
App?" — die Prüfung am Code gab ihm recht. Das Programm hing an **einer**
Operation (`create_from_scad`), deren eigener Hinweis sie „die letzte Wahl,
nicht die erste" nannte; der Testfall, für den sie einmal *der* Weg war,
verbietet sie seit §30.1 ausdrücklich („jetzt kann `sketch_loft` ihn im
Haus"). In 39 Referenzanfragen kam sie nie vor, in keinem Beispielprojekt und
in keiner Regel. Dem gegenüber standen 599 Zeilen Backend und die einzige
Stelle, an der fremder Quelltext ausgeführt wurde.

Entfernt sind Operation, Backend, Registereintrag und die Einträge in
`discover`, `install`, `tools` und `foreign`; der Systemprompt steht auf
Version 4 mit **drei** statt vier Gewohnheiten, die Regelsammlung auf Version
3. `to_scad()` bleibt — es schreibt eine Datei und führt nichts aus.

Alte Projektdateien öffnen weiter: Migration 12 → 13 lässt einen
`create_from_scad`-Schritt stehen und hält die Auswertung an ihm an, statt sie
abzubrechen. Der Rest der Szene rechnet, der Prüfbericht nennt den Schritt.
Vorher gab dieselbe Datei einen **Programmfehler**-Dialog samt
Fehlerbericht-Knopf — für etwas, das der Kunde selbst gebaut hatte.

- [x] **Ein Schritt, den diese Fassung nicht rechnen kann, ist keine
      Sackgasse mehr (29.08.2026).** *Werte ansehen* zeigt seine rohen
      Parameter — bei einer Datei aus 0.1.3 auch das erhaltene
      OpenSCAD-Programm. Im Verlauf lässt er sich nun aus der Mitte löschen.
      Eine Nachfrage nennt abhängige Schritte und Strg+Z; das Löschen selbst
      ist genau eine Transaktion. Spätere Schritte mit derselben Objektkennung
      bleiben, Nutzer einer entfallenen frischen Ausgabe gehen gemeinsam mit,
      unabhängige Zweige nicht. Die gelöschte Ursprungszeile bleibt
      durchgestrichen sichtbar, und Format v17 erhält beide Seiten für Undo
      und Redo über Speichern und Öffnen hinweg.

## Der Leistungstest riss viermal und wurde von selbst wieder grün (26.08.2026)

`orient_200` misst die Orientierungssuche über 200 Kandidaten
(`search(mesh, count=200, layer_height=0.4)` auf `plate_holes.stl`, also
Schichtanalyse je Kandidat). Der Test riss in zwei Sitzungen viermal in Folge —
und wurde danach in zwei vollständigen Torläufen von selbst wieder grün, was
die Überschreitungszählung zurücksetzte.

Sechs Messungen, alle unter dem Schloss, vier davon bei bestätigt ruhiger
Maschine:

| Lauf | Wert |
|---|---|
| Bestmarke (`tests/.performance.json`, `orient_200 → alone`) | 15 151 ms |
| Regressionsschwelle (25 %) | 18 939 ms |
| ce, unter Restlast | 18 958 ms |
| ce, bei bestätigt 0 % CPU | 19 568 ms |
| a2, allein | 19 442 ms |
| a2, allein | 19 804 ms |
| ce, vollständiger Torlauf | darunter — grün |
| a2, vollständiger Torlauf | darunter — grün |

**Der Wert liegt nicht über der Schwelle, er liegt auf ihr.** Darauf kommt es
an: Vier Läufe darüber und zwei darunter bedeuten etwas anderes als eine
stabile Verschlechterung. Wer den Punkt als „langsamer geworden" liest, sucht
eine Ursache im Code; wer ihn richtig liest, prüft zuerst die Bestmarke.

**§31 ist nicht gerissen.** Die Zusage lautet „unter 20 Sekunden", und das hält
jede einzelne Messung. Was fehlt, ist Abstand — gut zwei Prozent statt
fünfundzwanzig. Der Test wird deshalb sporadisch rot, ohne dass sich eine Zeile
geändert hätte, und das ist der eigentliche Schaden: Ein Test, der ohne Anlass
rot wird, verliert seine Aussagekraft.

**Entschieden wird das nicht durch einen weiteren Lauf gegen den heutigen
Stand**, sondern durch eine Messreihe gegen einen **älteren**. Sie trennt die
zwei Möglichkeiten: Entweder stammt die Bestmarke aus einem besonders ruhigen
Lauf und ist als Vergleichspunkt zu scharf, oder der Pfad ist tatsächlich
langsamer geworden. Im Pfad liegen mehrere Commits der letzten Tage, darunter
`202739ae` und `3c1b7306`.

- [x] **`orient_200` gegen einen älteren Stand messen — gemessen am
  30.08.2026, und die Bestmarke war zu scharf.** Die Messreihe lief gegen
  `1f3426eb` in zwei eigenen Arbeitsbäumen auf ruhiger Maschine: 18 682 ms
  alt gegen 18 774 ms neu — beide Reihen liegen gleich, der Pfad ist nicht
  langsamer geworden. Die Auflösung samt der Mechanik dahinter steht im
  Abschnitt „Sechs Leistungsmarken rissen einen Zähler, und der Code war
  unschuldig (30.08.2026)".

**Ausgeschlossen ist die Marker-Härtung vom selben Tag** (`3ef11e6e`): gemessen
kostet `trial_days_left` kalt 86 ms und warm unter 6 ms, und die
Orientierungssuche ruft `activation` nicht. Die Werte lagen schon vor diesem
Commit in derselben Höhe.

Die allgemeine Lehre steht in `.claude/rules/tests.md` (`d7df8535`): Die
Zweimal-Regel fängt Fremdlast, aber keinen Wert, der um die Schwelle streut.

## Das Handbuch-PDF druckt seine Bilder nicht mit (26.08.2026)

`tools/make_manual.py` schreibt das Handbuch als Website-Seite **und** als PDF
nach `Releases/Solidon3D-Handbuch-<sprache>.pdf`. Die PDFs entstehen, sind
vollständig gesetzt und tragen ihre Schriften — aber **kein einziges Bild**.
An jeder Abbildung steht eine Lücke in exakt ihrer Größe: Das Layout kennt das
Bild, die Pixel fehlen.

Gemeldet hat es Robert am 26.08.2026 an den erzeugten Dateien. Es ist **kein
Auslieferungsfehler**: Die PDFs sind nirgends verlinkt, liegen nicht unter
`website/` und reisen nicht im Paket mit; das Handbuch **im Programm** ist
sauber, weil der Viewer je Anzeige frisch von Platte lädt und SVG selbst
rendert. Betroffen ist allein der Druckweg.

**Was gemessen und ausgeschlossen ist:**

| Vermutung | Messung |
|---|---|
| Bildpfade falsch | nein — `handbuch/de/…` bzw. `../handbuch/en/…`, beide korrekt relativ |
| Bilder laden nicht | nein — 39 von 39 `complete` mit `naturalWidth > 0` |
| `@media print` versteckt sie | nein — der Druckblock setzt nur Größen, kein `display: none` |
| Ruhezeit zu kurz, `decode()` abwarten hilft | nein — das Promise löst **nie** auf, auch mit `loading="eager"` und neu gesetztem `src` |
| `runJavaScript` wartet auf das Promise | **nein** — es gibt den synchronen Wert zurück (gemessen: `''`), der Rückruf kommt sofort |
| Kein Viewport, weil `QWebEnginePage` ohne View | nein — eine `QWebEngineView` mit 1200×1600 und drei Sekunden Ruhe druckt genauso ohne Bilder |

**Dazu ein zweiter Fehler, der den ersten verdeckt hat.** Es gibt zwei
Druckanläufe, der zweite mit mehr Ruhezeit — er läuft nie. `attempt` gilt als
gelungen, sobald `printToPdf` Bytes liefert, und ein PDF ohne Bilder ist auch
Bytes. Die Absicht stand im Kommentar, die Bedingung hat sie nie geprüft.

- [x] **Bilder im Handbuch-PDF** — gefunden und behoben am 27.08.2026
  (`24967dfc`). **Es war keine der sechs ausgeschlossenen Vermutungen und
  auch keine der zwei offenen.** Die Abbildungen steigen am Bildschirm beim
  Lesen ein Stück auf, und diese Animation hängt an der Scroll-Position:

      @supports (animation-timeline: view()) {
        @media (prefers-reduced-motion: no-preference) {
          main figure { animation: rise linear both;
                        animation-timeline: view(); }
        }
      }

  Gedruckt wird nicht gescrollt. Der Fortschritt bleibt null, die Animation
  steht auf ihrem Anfangswert, und der ist unsichtbar. **Deshalb hat jede
  Prüfung auf den Ladezustand die Seite für gesund erklärt** — die Bilder
  luden ja alle, 39 von 39 mit `naturalWidth > 0`. Sie wurden nur nie
  gezeichnet. Und deshalb griff auch die Prüfung auf `display: none` daneben:
  Die Regel versteckt nichts, sie animiert nur.

  Der Fix steht im `@media print`-Block von `tools/make_manual.py`:
  `main figure { animation: none !important; }`

  **Gemessen an derselben Seite**, gleicher Lauf, nur das Stylesheet
  verändert:

  | Fassung | PDF | Rasterbilder |
  |---|---|---|
  | Original | 703 KB | 0 |
  | ohne diese eine Regel | 4116 KB | 18 |
  | ohne Stylesheet ganz | 3711 KB | 18 |

  Gefunden durch **Halbierung des Stylesheets**, nachdem Raten dreimal
  danebenlag (`loading="lazy"`, `@media print` als Ganzes, die
  `max-height`-Regeln — alle drei einzeln getestet, alle drei folgenlos).
  Vorher war der Mechanismus vollständig entlastet worden: PNG und SVG, aus
  `file://` wie aus `data:`, 8 KB bis 1,3 MB, ein Bild bis neununddreißig,
  Unterordner, Ruhezeit 400 ms wie 1200 ms — in jedem dieser Fälle trägt
  `printToPdf` das Bild mit.

  **Zur Erfolgsbedingung, die der Punkt verlangt hat:** Ein Grep auf
  `/Subtype /Image` findet auch über einem **guten** PDF null, sobald das Bild
  ein SVG ist — SVG wird als Vektorgrafik eingebettet, nicht als Rasterbild.
  Das Handbuch bindet 8 PNG und 31 SVG ein; wer nur den Grep zählt, hält ein
  gesundes PDF für kaputt. Tauglich ist er nur zusammen mit der Dateigröße
  gegen eine Grundlinie **mit demselben Text** (die eingebetteten Schriften
  wiegen schwerer als ein kleines Bild und drehen den Vergleich sonst um).

  **Erledigt am 28.08.2026:** `tools/make_manual.py` hat alle sechs HTML-Seiten
  und alle sechs PDFs neu erzeugt. Jede Sprachfassung trägt 33 Abbildungen,
  davon 25 mit eigener dunkler Variante; die PDF-Prüfung fand auf zusammen
  709 Seiten keine leere Seite und kein Zeichen außerhalb des A4-Satzspiegels.

## Was Robert am 26.08.2026 aufgetragen hat

Zwei Aufträge aus dem Tag der 0.2.0-Veröffentlichung, beide von Robert selbst.
**Der erste ist gebaut** (Stand 28.08.2026): Modell und Übergabe standen seit
`1261935f`; der Filamentwähler trägt nun auch die Oberfläche. Name und Farbe
identifizieren die Spule unabhängig von der Extruderreihenfolge, und der
direkte 3MF-Export schreibt ihre Werte ebenso je Extruder wie die Übergabe an
den Slicer.

- [x] **Einstellungen je Filament.** Solidons eigene Felder — Temperaturen,
  Kühlung — sollen sich **je Materialslot** übersteuern lassen, und die
  Übergabe an den Slicer soll sie je Extruder mitgeben. Die Grenze ist dabei
  die Sache selbst: übersteuerbar ist, was **an der Spule hängt** und sich
  physikalisch von Filament zu Filament unterscheidet. Geometrie gehört nicht
  dazu — Wandstärken und Schichthöhen sind Eigenschaften des Teils und nicht
  des Materials, und ein Feld, das beides vermischt, macht aus einem
  zweifarbigen Teil zwei verschiedene Teile.

  **Gebaut und geprüft am 28.08.2026:** Am benutzten Filament öffnet
  „Druckwerte …“ einen gestuft tiefen Dialog für Temperatur, Kühlung, Rückzug
  und Materialwerte. Ausgeschaltete Gruppen bleiben bei den Projektwerten;
  eingeschaltete gelten nur für diese Spule. Der direkte 3MF-Export und der
  Reimport bewahren Namen und Farbe, Orca erhält die Werte je Extruder. Ein
  gewähltes Herstellerprofil ergänzt die Spule, überdeckt aber keine
  ausdrückliche Kundenwahl.

- [ ] **Am 15.10.2026 die Verkaufsbereitschaft prüfen.** Sind Finanzamt und
  Merchant of Record bis dahin durch, folgt spätestens am 25.10. der
  Verkaufsbau: `DEMO_UNTIL = None`, `TRIAL_FROM = None`, Rechtstexte und
  Website in Gegenwartsform. Das ist kein Serverschalter — beide Werte sind
  einkompiliert, und der Update-Hinweis braucht eine Woche Vorlauf, damit er
  die Kunden **vor** dem 31.10. erreicht.

  **Entscheidung Robert, 28.08.2026:** Verkauf ab 01.11.2026, zunächst ohne
  zusätzliche Testphase. Sind die äußeren Voraussetzungen am 15.10. nicht da,
  wird die Demo deshalb nicht stillschweigend verlängert. Dann hält dieser
  Punkt an und verlangt eine neue ausdrückliche Entscheidung; andernfalls
  stünde bei jedem Kunden ab 31.10. eine abgelaufene Anwendung, obwohl noch
  nichts gekauft werden kann.

## Dieselbe Zugabe, zwei Zahlen (27.08.2026)

Beim Zusammenlegen der Konstanten-Zwillinge (57200cb9) blieb einer bewusst
stehen, weil er keine Aufräumarbeit ist, sondern eine Messung verlangt.

- [x] **Die Boolesche Zugabe ist 0,05 mm und 0,01 mm.** Wie weit ein
  abziehendes Werkzeug über die Fläche hinausreichen soll, die es
  durchschneidet — zusammenfallende Flächen sind der klassische Weg, eine
  Boolesche Operation zu brechen (§39). `geom/boolean.BOOLEAN_OVERLAP` sagt
  0,05, `knowledge/parts/shapes.OVERLAP` sagt 0,01, und beide Kommentare
  begründen es mit demselben Satz.

  Die Frage ist nicht, welche Zahl schöner ist, sondern **welche die kleinere
  ist, die noch trägt**: Ist 0,01 zu knapp, scheitern Boolesche Operationen an
  Bausteinen sporadisch — sporadisch, weil es von der Vernetzung des
  Einzelfalls abhängt, und das ist die teuerste Sorte Fehler. Ist 0,05 mehr
  als nötig, trägt jede Beschriftung und jede Textur 0,05 mm zu viel ab; bei
  einer 0,2-mm-Gravur ist das ein Viertel.

  Gemessen wird an beiden Enden: die Rückfallkette über den Korpus mit
  abgesenkter Zugabe (ab wann greift Stufe 2), und die abgetragene Menge einer
  Gravur gegen ihre Solltiefe. Danach eine Zahl an einer Stelle — bis dahin
  hält der Kommentar in `boolean.py` die Abweichung sichtbar, statt sie
  stillschweigend anzugleichen.

  **Fortschreibung 27.08.2026, und der Punkt ist dringlicher geworden:** Es
  sind inzwischen **drei** Stellen, und zwei davon tragen denselben Namen mit
  verschiedenen Zahlen —

      geom/boolean.py         BOOLEAN_OVERLAP = 0.05   -> label_ops, texture_ops
      geom/prepare.py         BOOLEAN_OVERLAP = 0.01   -> lid, knowledge/parts/ops
      knowledge/parts/shapes.py   OVERLAP     = 0.01

  Der mittlere kam am selben Tag dazu (`f934a422`, 15:38) und beruft sich im
  Kommentar auf denselben §39 wie der obere. Damit hängt es am Importpfad,
  welche Zugabe eine Operation bekommt: `from app.core.geom.boolean import
  BOOLEAN_OVERLAP` gibt 0,05, `from app.core.geom.prepare import
  BOOLEAN_OVERLAP` gibt 0,01. Wer den Namen liest, sieht den Unterschied
  nicht.

  **Gemessen und geschlossen am 27.08.2026 (`1594fd8c`).** Die Messung hat die
  Frage verschoben: nicht „welcher Wert ist richtig", sondern „wirkt der Wert
  überhaupt".

      neun koplanare Lagen x {0,05 | 0,01 | 0,0}   alle direct, alle dicht,
                                                   alle exakt, kein Rückfall
      Gravur 0,2 mm  x {0,05 | 0,01 | 0,001 | 0,0} alle 2,6221 mm3 Abtrag

  `manifold3d` ist feste Abhängigkeit und rechnet zusammenfallende Flächen
  robust; der Bruch, gegen den die Zahl gebaut wurde, gehört zu einem Kern,
  den es hier nicht mehr gibt. Und die Zugabe liegt außerhalb des Materials —
  das Werkzeug wird um sie länger **und** um sie angehoben. Damit ist auch die
  Sorge widerlegt, die diesen Punkt aufgemacht hat: 0,05 trägt bei einer
  0,2-mm-Gravur nichts zu viel ab.

  Eine Zahl, 0,01, in `geom/boolean.py`. Der kleinere gewinnt, weil er
  gebunden ist: In `knowledge/parts/ops.py` ist dieselbe Zahl die Schwelle,
  an der ein Baustein als „baut nach oben" statt „trägt ab" gilt, und sie muss
  den Einsinkbetrag knapp überdecken, den derselbe Wert erzeugt.

  Behalten wird sie trotzdem — die Rückfallkette hat Stufen unterhalb von
  `manifold3d`, und eine Zugabe, die nachweislich nichts kostet, ist billiger
  als die Frage, ob eine davon sie doch braucht.

---

## Die Auswahl wird gekürzt und niemand sagt es (27.08.2026)

Gefunden beim Durchsehen der Zwillingspaare, aber es ist keiner: Der Fall
betrifft beide Kerne gleich.

- [x] **Wer drei Körper auswählt und „Abziehen“ klickt, bekommt zwei verrechnet
  und keinen Hinweis auf den dritten.** `inputs_for` in
  `app/ui/main_window.py:646` schneidet die Auswahl auf das zu, was die
  Operation deklariert — `tuple(selected[: spec.consumes])`. Für Vereinigen,
  Abziehen und Schnittmenge sind das zwei. Der dritte Körper bleibt unverändert
  in der Szene stehen: richtig gerechnet, nur ungefragt.

  `tests/test_whole_scene_ops.py:122` hält das Verhalten ausdrücklich fest —
  drei Objekte hinein, die ersten beiden heraus. Es ist also gewollt und kein
  Versehen. Die offene Frage ist nicht, ob gekürzt wird, sondern **ob der Kunde
  es erfährt**: Er sieht einen Körper, der übrig blieb, und kann nicht
  unterscheiden, ob die Operation ihn übergangen hat oder ob er selbst falsch
  geklickt hat. Nach Roberts Maßstab — muss der Kunde raten, ist es falsch —
  fehlt hier eine Zeile.

  Drei Wege standen offen: ein Befund nach der Operation, eine Sperre im Menü,
  oder die bewusste Entscheidung, dass die Klickreihenfolge Antwort genug ist.

  **Es war ein vierter (`8ac1438b`, 27.08.2026): Die Anwendung schweigt gar
  nicht.** Der Hinweis steht seit je im Dialog — `_works_on` baut ihn,
  `OperationDialog` zeigt ihn, und bei drei gewählten Körpern und einer
  Zwei-Körper-Operation stand dort „Angewendet wird auf die 2 zuerst gewählten
  von 3". Gemessen, nicht gelesen: Aus dem Code sieht das Kürzen tatsächlich
  stumm aus, weil die Auskunft eine Ebene höher entsteht.

  Was fehlte, lag feiner. Bei **einem** Eingang nannte der Satz den Körper beim
  Namen, bei zweien nicht — und damit musste der Kunde seine eigene
  Klickreihenfolge erinnern, ausgerechnet dort, wo sie zählt: Die Booleschen
  sagen zu, dass „das zuerst angeklickte mit seinem Namen und Material bleibt".
  Jetzt steht dort „Angewendet wird auf Klotz und Stift — die 2 zuerst
  gewählten von 3".

## Was die Zwillingsdurchsicht in der Oberfläche liegen ließ (27.08.2026)

Robert hat gefragt, warum es so viele Zwillinge gibt und ob wir sie brauchen.
Die Antwort auf die vier `MENU_TWINS` steht weiter unten; hier stehen die
Funde derselben Durchsicht, die **keine** Rechenkern-Paare sind, sondern
Auskünfte, die an mehr als einer Stelle hergeleitet werden.

Sieben davon liefen bereits auseinander und sind behoben (Volumen im Chat,
Kürzel der Ansichtsleiste, Kantenwinkel, Menügrenze, Befundzeile gegen
Tooltip, Druckdauer, Körperfarbe im hellen Thema). Zwei bleiben offen, weil
sie heute **noch** dasselbe sagen — sie sind Schuld, kein Fehler.

- [x] **Zeichenwerkzeuge heißen in der Kürzelübersicht anders als am Knopf.**
  `shortcuts_window._drawing_keys` führt eine eigene `titles`-Tabelle;
  `sketch_editor` beschriftet seine Knöpfe daneben. Zwei Namen weichen heute
  ab (`fit`: „Alles einpassen" gegen „Einpassen", `rectangle` mit und ohne
  Maßangabe), der Rest stimmt.

  Der eigentliche Schaden war die Bauart: `titles.get(name)` ließ einen
  unbekannten Schlüssel **stillschweigend fallen**. Ein neues `TOOL_KEYS`-
  Werkzeug verschwand damit aus der Übersicht, ohne dass etwas rot wurde.

  **Behoben am 27.08.2026.** Ein Schlüssel ohne Titel taucht jetzt mit seinem
  Schlüssel auf, statt zu verschwinden — dieselbe Haltung wie bei
  `group_title` im Register: „Eine neue Kategorie soll auftauchen und nicht
  verschwinden." Ein roher Schlüssel in der Übersicht ist hässlich und wird
  gesehen; eine fehlende Zeile nicht. Dazu eine Zeile im vorhandenen Test, die
  daraus einen roten Lauf macht: Er prüfte bisher, dass jede *Taste* vorkommt,
  nicht dass sie einen *Namen* hat. Gegenprobe gefahren — ein Werkzeug ohne
  Titeleintrag lässt ihn fallen und nennt es beim Namen.

  Die zwei abweichenden Namen (`fit`, `rectangle`) bleiben: Sie sind
  ausführlicher als am Knopf, und das ist in einer Übersicht richtig.

- [x] **Thema und Navigationsschema haben zwei Vokabulare — geschlossen am
  28.08.2026.** Das Ansichtsmenü
  sagt „Dunkles Thema" und „Navigation: Cura", der Einstellungsdialog „Dunkel"
  und „Wie in Cura — links wählt, rechts dreht". Sechs Schlüssel, zwölf Texte,
  zwölfmal fünf Kataloge — und einer der beiden Sätze für `slicer` wurde
  einmal berichtigt, der andere nicht.

  Beide nennen erkennbar dasselbe (in beiden steht „Cura"), deshalb ist es
  kein Fehler und steht hier unten. Es ist Pflegeaufwand: Beide Orte sind
  zugleich der Ort, an dem der Kunde das Schema *lernt*, und der Nächste, der
  einen der zwölf Texte schärft, schärft ihn an einer Stelle.

  Menü und Einstellungsdialog lesen jetzt beide `THEMES` und `NAVIGATION` aus
  `settings_dialog.py`; das Ansichtsmenü hat dafür ein eigenes Themen-Untermenü.
  Ein Oberflächentest vergleicht Kennungen und sichtbare Texte beider Wege.

---

## Der Slicer-Name stand da, wo eine Eigenschaft gemeint war (27.08.2026)

Roberts Auftrag: „Die teureren Zwillinge sind unsichtbar: die drei
Slicer-Familien. 24 Verzweigungen im Code, schauen ob wir das sauber
hinbekommen."

Gemessen sind es **26** — jede `if`, jeder bedingte Ausdruck und jedes
Wörterbuch in `app/` und `tools/`, in dessen Test ein Familienname als
Zeichenkette steht:

| Datei | Verzweigungen |
|---|---|
| `app/core/export/handover.py` | 15 |
| `app/ui/print_settings_dialog.py` | 4 |
| `app/core/export/slicer_profiles.py` | 3 |
| `app/core/export/slicer_keys.py` | 2 |
| `app/core/export/writer.py` | 2 |

**Der Schnitt selbst ist richtig, und das ist gemessen und nicht angenommen.**
`slicer_keys.FLAVOUR_BY_NAME` bildet ElegooSlicer, Bambu Studio und
SuperSlicer auf die drei Familien ab; gegen den echten ElegooSlicer gefahren
findet Solidon 3887 Profile und erkennt Roberts Drucker als `Elegoo Centauri
Carbon 2 0.4 nozzle`. Eine vierte Familie einzuführen wäre also falsch — die
Abstraktion trägt.

**Was nicht trägt, ist die Form der Frage.** Elf der Verzweigungen fragen
`== "orca"` oder `!= "orca"`, und **jede meint eine andere Eigenschaft**. Der
Kommentar daneben nennt sie jedes Mal, der Code prüft jedes Mal den Namen:

- `handover.py:854` — „Nur diese Familie liest Einstellungen aus der 3MF"
- `handover.py:1213` — führt eigene Filamentprofile
- `handover.py:690` — kennt mehrere Materialslots
- `slicer_profiles.py:103` und `:138` — hat einen Nutzerprofilbaum unter APPDATA

**Die richtige Form kennt der Bestand:** `slicer_keys.wants_bed_coordinates`
ist ein benanntes Prädikat mit Docstring. Genau eines gegen 26 Verzweigungen —
jemand hat sie einmal gewählt und dann nicht fortgesetzt.

Behoben ist bisher der eine Fall, in dem beide Formen **nebeneinander**
standen: `bed_box` verglich den Namen und meinte damit wörtlich dasselbe wie
das Prädikat zwei Dateien weiter (`0040f0fc`).

- [x] Die verbleibenden Namensvergleiche auf benannte Prädikate stellen, dort
  wo die Eigenschaft im Kommentar schon benannt ist. **Kein Fehlverhalten** —
  heute sagen alle Stellen dasselbe, weil alle drei Programme derselben
  Familie zugeordnet sind. Der Preis fällt an, wenn ein Fork in einer der elf
  Eigenschaften abweicht: Dann muss jemand elf Stellen finden und elf
  Entscheidungen einzeln treffen, die nie einzeln sichtbar waren.
  Nicht für jede Einzelstelle ein Prädikat — die drei Format-Zweige in
  `write_config` (INI, JSON, Kommandozeile) sind echte Dreiwege-Fälle und
  bleiben, wie sie sind.

---

## Was die Website-Durchsicht liegen ließ (27.08.2026)

Robert hat aufgetragen: „kontrollieren die webseite und das Handbuch ob alles
leicht verständlich, bei Sinn mit Bildern leicht erklärt ist und auch alles
wirklich auf dem neusten Stand ist, und ob noch etwas weiter optimiert werden
kann davon — wir wollen eine hoch innovative moderne app sein und kein 0815
Eindruck machen." Das Handbuch hat eine Nachbarsitzung genommen; hier steht,
was an der Website offen blieb.

Behoben und committet sind die messbaren Funde: die Handybreite (`ead6f96d`),
drei falsche Zahlen samt Wächter (`4a2ff103`), drei Zusagen der
Datenschutzerklärung gegen den Code (`04317c75`) und die Kartenangabe der
Messwerte (`00156df3`).

**Die Lehre des Tages steht über allen Punkten hier:** Der User-Agent-Fund war
am 25.08.2026 schon einmal gefunden und in einem Durchsichtsbericht als
„VERIFIZIERT" notiert worden. Ins Register kam er nie, und deshalb stand der
Rechtstext zwei Tage länger falsch da. Ein Fund, der nur in einem Bericht
steht, ist kein festgehaltener Fund.

- [x] **Beide Aufmacher stehen zur Hälfte leer.** `funktionen.html` und
  `ki-modelle.html` beginnen mit einer Überschrift links, zwei bis drei Zeilen
  darunter und nichts rechts. Bei `funktionen.html` verspricht die Unterzeile
  wörtlich „Jede Funktion mit einem Bild aus der laufenden Anwendung" — und
  genau darüber steht keines. Auf `ki-modelle.html` läuft die Seite über
  2400 px reinen Text und zwei Tabellen, bevor das erste Bild kommt.

  **Das ist der teuerste Einzelpunkt der Durchsicht**, weil der Aufmacher
  entscheidet, ob weitergelesen wird. Die Startseite macht es richtig vor: Sie
  trägt das Anwendungsfenster rechts neben dem Text.

  **Halb erledigt, und das steht hier statt eines Hakens** (`5f502c8d`):
  Die beiden **deutschen** Seiten tragen den Aufmacher, die **zehn
  Übersetzungen nicht** — dort steht weiter `h1` mit `p.sub` und nichts
  rechts daneben. Der Commit hat alle zwölf Dateien angefasst, aber nur mit
  den Fußzeilen aus dem Handy-Punkt; der Aufmacher blieb bei den zweien, an
  denen er gebaut wurde. Ein Kunde auf `/en/features.html` sieht unverändert
  genau das, was dieser Punkt beschreibt.

  Gefunden hat es die Nachbarsitzung, weil sie `class="hero"` über **alle
  zwölf** Dateien gezählt hat statt über die zwei, die geändert worden waren.
  Die Lehre ist billiger als der Fehler: **Wer eine Seite in sechs Sprachen
  pflegt, zählt nach der Änderung über alle sechs** — der eigene Diff zeigt,
  was man angefasst hat, nie was fehlt.

  **Und der Rest wartet auf ein Bild, das es noch nicht gibt** (Entscheidung
  Robert, 27.08.2026): Kein vorhandenes Motiv wird recycelt — der Aufmacher
  von `ki-modelle.html` soll ein KI-Modell **in der laufenden Anwendung**
  zeigen, nicht freigestellt auf Weiß wie die sechs Tonrenderings. Das löst
  zugleich eine Doppelung, die sonst bliebe: `weg-2-schnitt.webp` stünde
  zweimal auf derselben Seite, 1500 px auseinander. Der Weg zu dem Bild ist
  Weg 3 selbst, und ihn zu fahren ist die zweite Hälfte des Auftrags — eine
  Abbildung aus der laufenden Anwendung entsteht nur, wenn der Weg für einen
  Kunden wirklich läuft.

  **Erledigt am 27.08.2026** (`fdb957b3`, `bb1bd0cc`). Alle zwölf Seiten
  tragen den Aufmacher; gezählt wird über alle zwölf, und der Einbau
  bricht ab, wenn es weniger sind. Das Motiv der KI-Seiten ist über
  Weg 3 entstanden — erzeugt, auf Maß gebracht, aufs Bett gesetzt — und
  das Modell liegt als `tools/data/generated-owl.glb` im Repository,
  damit das Bild ohne ComfyUI in jeder Sprache neu entsteht. Was das
  wert ist, zeigte sich eine Stunde später: Der dreifache Hinweis im
  Prüfbericht wurde behoben (`c5ade5f1`), ein Lauf, und alle sechs
  Belege stimmten wieder.

- [x] **Jede Abbildung mit eingebettetem Text ist auf dem Handy unlesbar.**
  Sie skalieren gleichmäßig herunter statt umzubrechen; bei 390 px landen die
  Beschriftungen bei 5 bis 7 Bildpunkten. Am schwersten wiegt der
  Prüfbericht-Ausschnitt auf `funktionen.html`: Das Bild trägt die vier
  Befundzeilen, um die es im ganzen Abschnitt geht, und keine ist zu
  entziffern. Ebenso Bausteinkatalog, Bohrdialog, Schichtanalyse.

  **Entschieden von Robert am 27.08.2026: nur Antippen**, keine eigenen
  Handyfassungen. Umgesetzt in `2beeeeed` — 50 Bildschirmfotos über achtzehn
  Verkaufsseiten tragen einen Verweis auf sich selbst, der Weg von `235d7050`
  (kein JavaScript, keine Lightbox, der Browser zoomt selbst). Dazu `.stage a`
  in `style.css`: `display: block`, kein Unterstrich, keine Linkfarbe,
  `cursor: zoom-in`.

  **Ein Zwischenschritt war meiner und falsch, und er steht hier, weil er
  sich fast durchgesetzt hätte.** Ich hatte zwei Sitzungen geschrieben, eine
  Regel, die `figure` aus dem Textrahmen ausbrechen lässt, bringe „40 bis 80
  Bildpunkte, ohne dass ein Bild neu entsteht" — von der Startseite
  übertragen, wo ich es gemessen hatte, auf die Funktionsseite, wo ich es
  nicht gemessen hatte. Die Bühne misst dort schon 341 bis 353 px bei 375 px
  Fenster; der Ausbruch brächte 29 Bildpunkte und aus 3,3 px Schrift 3,6.
  Beide Sitzungen hätten es übernommen, ohne nachzurechnen.

  **Was offen bleibt und bewusst so entschieden ist:** Der Leser muss tippen,
  auch beim Prüfbericht, dessen vier Befundzeilen der Abschnitt daneben
  bespricht. Ein Ausschnitt wäre dort ohne jede Handlung lesbar gewesen; die
  Entscheidung lautet, dass das den Bilderlauf nicht wert ist.

- [x] **Der Abschlussknopf der Startseite führt zu einer E-Mail, nicht zur
  Demo.** Unter „Das nächste Teil, das passt" stand als Hauptknopf
  `support@solidon3d.de`. Wer bis dorthin gescrollt hat, ist überzeugt und
  will laden.

  **Entschieden von Robert am 27.08.2026: Demo als Hauptknopf**, Support
  daneben als zweiter. Umgesetzt in `2beeeeed`, in allen sechs Sprachen — mit
  den Beschriftungen, die auf den Funktionsseiten derselben Sprache schon
  standen („To the demo", „A la demo", „Vers la démo", „Alla demo", „Para a
  demo"). Neu formuliert wurde nichts. Das Handbuch bleibt als dritter Knopf
  stehen: Es wegzunehmen war nicht Teil der Entscheidung.

  **Der Fund saß nur auf den sechs Startseiten** — `funktionen.html` und
  `ki-modelle.html` trugen seit je „Zur Demo" als Hauptknopf. Falsch war also
  ausgerechnet die Seite, auf der die meisten ankommen.

- [x] **Die zwei Tabellen auf `ki-modelle.html` brechen auf halber Breite ab
  — geprüft und verworfen.** Der Befund stimmte in seiner Zahl und in seinem
  Schluss nicht: Ja, die Tabellen messen 736 px unter 1176 px Text. Aber sie
  brauchen die Breite nicht, sondern haben schon zu viel davon.

  Gemessen wurde die erste Spalte gegen ihren längsten Eintrag, ohne Umbruch:

  | | Spalte 1 hat | braucht |
  |---|---|---|
  | Vergleichstabelle (3 Spalten, 11 Zeilen) | 464 px | **316 px** |
  | Zeitentabelle (2 Spalten, 6 Zeilen) | 592 px | **286 px** |

  Die übrigen Spalten stehen fest auf 8,5 rem. Eine Verbreiterung auf 1176 px
  gäbe der ersten Spalte 904 px für 316 px Text — das Auge müsste vom Namen
  links bis zum Häkchen rechts über eine halbe Bildschirmbreite wandern, und
  genau daran verliert man in einer Vergleichstabelle die Zeile. `max-width:
  46rem` ist deshalb richtig, auch ohne Begründung im Kommentar daneben.

  **Was am Befund stimmte, war der Eindruck** — 440 px Weißraum rechts neben
  dem Kerninhalt sehen nach Versehen aus. Das ist eine Frage der Anordnung
  (zentrieren, oder den Raum mit etwas füllen, das dorthin gehört) und keine
  der Tabellenbreite. Wer ihn aufnimmt, fängt nicht bei `max-width` an.

  **Und es ist der zweite Agentenbefund des Tages, der einer Messung nicht
  standhält** — nach den „41 Minuten", bei denen der volle statt des kompakten
  Werkzeugsatzes gerechnet wurde. Beide Male klang die Beobachtung richtig und
  war es auch; falsch war der Schluss daraus, und beide Male hätte eine
  einzige Messung ihn verhindert.

- [x] **Auf dem Handy sind die Unterseiten eine Sackgasse.** `funktionen.html`
  blendet bei 390 px „Vier Wege" und „KI-Modelle" aus (`hide-small`,
  `hide-tiny`), es gibt kein Ersatzmenü, und die Fußzeile führt beide nicht.
  Vom Handy aus kommt man von dort nur über den Umweg Startseite hin.

  **Auf der Startseite ist dasselbe kein Fehler** und bleibt: Dort führt der
  Demo-Knopf selbst auf `#preis`, und „Funktionen" steht als eigener Abschnitt
  auf derselben Seite. Der Unterschied ist, dass die Unterseiten kein solches
  Ersatzziel haben.

- [x] **„Eine Grafikkarte mit 8 GB Speicher" ist nie gemessen worden.** Die
  Systemvoraussetzungen nennen sie als Mindestanforderung fürs Generieren. Die
  Gewichte allein sind 7,5 GB, und gelaufen ist der Weg hier nur auf einer
  RTX 4080 mit 16. Die Messangabe daneben ist am 27.08. berichtigt worden
  (`00156df3`) — diese hier nicht, weil eine ungemessene Zahl durch eine
  andere ungemessene zu ersetzen nichts gewinnt.

  **Gestrichen am 27.08.2026** (`fe51f282`, Entscheidung Robert): nicht als
  Erfahrungswert gekennzeichnet, sondern weg — „keine Angabe ist
  besser als eine falsche“. An ihre Stelle tritt die Formulierung, die
  im Fließtext derselben Seite schon stand („eine kräftige
  Grafikkarte“), in jeder Sprache bereits übersetzt. Damit sagen Absatz
  und Tabelle zum ersten Mal dasselbe; vorher nannte der eine keine Zahl und
  die andere eine.

- [x] **`PROMPT_TOKENS` ist mit allen 106 Werkzeugen nachgemessen.** `llm.py`
  nennt jetzt 23 891 Token für Systemprompt und kompakten Werkzeugsatz, und
  daraus folgen die 51 Minuten auf `ki-modelle.html` (23 891 / 7,8 / 60 =
  51,05). Gemessen am 28.08.2026 mit `qwen3:14b` über den echten
  `/api/chat`-Auftrag: 3 510 Zeichen Systemtext, 107 649 Zeichen Werkzeug-JSON,
  `prompt_eval_count = 23 891` und `prompt_eval_duration = 10,293 s` auf der
  aktuellen Grafikkarte.

  **Kein Fehlbefund der Seite**, und der Weg dorthin ist die eigentliche
  Lehre: Eine Durchsicht meldete die Zahl als grob falsch (76 bis 102 Minuten)
  — sie hatte den **vollen** Werkzeugsatz gerechnet, während der Ollama-Weg
  den kompakten fährt, und eine Schätzung gegen eine Messung gestellt.

  **Der Lauf vom 27.08.2026 entschied nichts.**
  Gemessen über `/api/chat` mit `num_ctx`, kompaktem Werkzeugsatz und einer
  Gegenprobe ohne `tools`:

  | | ohne `tools` | mit `tools` |
  |---|---|---|
  | `qwen3:14b` | 1066 | 3387 |
  | `qwen2.5-coder:14b` | 1064 | 3395 |
  | `gpt-oss:20b` | 975 | 1716 |

  Zwei 14b-Modelle stimmten auf zwanzig Token überein — und beide lagen bei
  einem Fünftel der eingetragenen 19 249. Der Widerspruch ist jetzt erklärt:
  Die damalige Gegenprobe schickte die Werkzeuge, aber nicht Solidons
  Systemprompt und reproduzierte damit nicht den Produktionsauftrag. Der
  vollständige Auftrag zählt die Werkzeugvorlage mit.

  Der kompakte Satz spart weiterhin 27 Prozent Zeichen gegenüber dem vollen.
  `PROMPT_TOOL_COUNT = 106` und ein Test machen jede weitere Operation jetzt
  zum roten Anlass für dieselbe Messung; damit altert die Kundenzahl nicht
  wieder unbemerkt.

- [x] **Vier Datumsangaben werden am 31.10.2026 still falsch.** „Die Demo
  läuft bis zum 30. Oktober" steht auf der Startseite in sechs Sprachen an
  mehreren Stellen, dazu eine FAQ-Frage „Was passiert am 30. Oktober?" und der
  Einführungspreis bis 31.01.2027. Die Umschaltung des Download-Kastens hat
  einen Test, diese Sätze nicht.

  **Gelöst am 27.08.2026** (`24c1323f`) und am 28.08. auf die gefallene
  Entscheidung nachgezogen: Verkauf ab 01.11. ohne zusätzliche Testphase,
  69 Euro bis 31.01.2027, danach 99 Euro. Geprüft wird, dass die bis dahin
  richtigen Zukunftssätze **rechtzeitig** in Gegenwartsform wechseln.
  `test_the_pages_do_not_promise_a_date_that_is_about_to_pass` wird fünf Tage
  vor dem Stichtag rot: Vorlauf genug, um zu entscheiden und in sechs Sprachen
  umzuschreiben.

  Er hängt an `DEMO_UNTIL` und nicht an einem zweiten Datum — wird verlängert,
  wandert die Erinnerung mit. **Nicht zu verwechseln mit dem Wecker in
  `test_activation.py`**: Der fragt, ob die Demo noch läuft, und wird am 31.10.
  rot; für die Website ist das der Tag zu spät.

  Der erste Anlauf übersprang sich selbst. `conftest` setzt `DEMO_UNTIL` für
  die ganze Suite auf `None` — sonst wäre sie ab dem Stichtag an Dutzenden
  Stellen rot —, und der Test las den Modulwert statt der Fixture
  `shipped_demo_until`. Er lief grün, ohne je etwas geprüft zu haben; verraten
  hat ihn allein das „1 skipped“ in der Ausgabe.

- [x] **Die EULA beschränkt auf einen Rechner, und der Code setzt das jetzt
  um.** Geräte-Zertifikat, Online- und Offline-Aktivierung, genau ein aktiver
  Geräteplatz sowie selbständige Deaktivierung sind gebaut und getestet.
  `EULA.md` 1.4, `AGB.md` 1.3, Datenschutzseite und Verkaufsseiten beschreiben
  denselben Stand: Installation auf den eigenen Rechnern, aber nur einer
  zugleich freigeschaltet; danach keine regelmäßige Lizenzabfrage.

- [x] **AGB § 2 trennte Demo und Verkaufstest nicht.** Die Demo läuft
  vollständig bis einschließlich 30.10.2026 und startet am 31.10. nicht mehr.
  Die Verkaufsversion wird ab 01.11.2026 zunächst ohne zusätzliche Testphase
  angeboten. `TRIAL_FROM = None` hält den weiterhin getesteten Testpfad sauber
  deaktiviert; eine spätere Fassung kann ihn ausdrücklich wieder einschalten.
  Das gesetzliche vierzehntägige Widerrufsrecht bleibt davon unberührt.


---

## Der erste Kundenbericht aus dem Feld (27.08.2026)

Simon Wenger, CachyOS mit GNOME auf Wayland, Solidon3D 0.1.5. Er konnte den
Bericht **nicht aus der Anwendung senden** und schickte ihn als Anhang an
Robert weiter, mit dem Satz „Ich kann den Bericht aus der App nicht senden:
urlopen error“.

Vier Befunde von ihm, zwei weitere fielen beim Lesen seines Berichts auf.
Robert hat entschieden: „jede plattform sollte das gleiche haben und alles
funktionieren“. Alle sechs sind behoben.

- [x] **Das Paket hatte kein Netz** (`c0f91f52`). Kein Versehen: Es stand als
  Entscheidung in der Roadmap, im Docstring des Erzeugers und als Zusicherung
  im Test. Die Begruendung „ohne Netz gibt es kein Konto, keine Telemetrie
  und keine Frage danach“ klang plausibel und war es nicht: **Die Zusage
  haengt an der Bauart, nicht an der Sandbox.** `support.send()` hat genau
  einen Aufrufer an einem Knopf, und Windows und macOS tragen dieselbe Zusage
  ohne jede Sandbox. Eine Grenze, die nur auf einer von drei Plattformen
  steht, ist keine Zusage, sondern ein Unterschied.

- [x] **Der Zeiger war doppelt so gross wie jeder andere im Bild**
  (`4605067a`). Die Groesse hing allein an der Zeilenhoehe mal zwei: bei 30
  Punkten ein Zeiger von 60, wo Systemzeiger 24 bis 32 messen. Wer die
  Schrift vergroessert, hat nichts ueber seine Zeiger gesagt. `XCURSOR_SIZE`
  gilt jetzt zuerst.

- [x] **Der Griffpunkt lag um den Ueberabtastungsfaktor daneben**
  (`ef28eed7`). Die Zeichnung entsteht mit 64 Pixeln fuer 32 angeforderte
  Punkte; der Griffpunkt wurde auf die angeforderte Groesse gerechnet. Die
  Pfeilspitze sitzt bei 15,6 Prozent der Kantenlaenge, der Griffpunkt lag bei
  7,8. **Der Test dafuer gab es schon und war zu locker** - er verglich mit
  `deviceIndependentSize()`, also mit derselben Annahme, die der Code traf.

- [x] **Der Fehlerbericht meldete vier Bibliotheken als nicht installiert**
  (`37a0b9b9`), darunter PySide6, ohne das kein Fenster aufgeht.
  `importlib.metadata` liest `.dist-info`-Ordner, und die reisen im
  PyInstaller-Bau nicht mit. **Ein Bericht, der etwas Falsches sagt statt
  „unbekannt“, schickt die Diagnose an eine Stelle, an der nichts ist** -
  beim Lesen dieses Berichts ist genau das passiert.

- [x] **Der Bericht sagte nichts ueber die Fenstersitzung** (`b21f8766`).
  Vier Umgebungsvariablen erklaeren beide Wayland-Punkte des Kunden, und
  keine stand drin. Auf Windows und macOS bleibt die Zeile weg, statt einen
  Strich zu zeigen.

- [x] **Die Eingabemethode war im Flatpak nicht erreichbar** (`b21f8766`).
  Sie spricht ueber den Sitzungsbus, und das Manifest gibt gezielten Zugriff
  statt des ganzen Busses - was nicht genannt ist, ist nicht erreichbar.

- [ ] **Ob die Eingabemethode im Flatpak jetzt erreichbar ist.** Die zwei
  `--talk-name`-Zeilen für Fcitx sind ergänzt und sind die üblichen aus
  Flathub-Manifesten; IBus liegt im Runtime und braucht keine eigene. Gebaut,
  **Bestätigung offen** — von Windows aus lässt sich das nicht messen. Es
  braucht eine Rückmeldung desselben Kunden oder ein Linux-Gerät.

- [ ] **Ob der Start auf Wayland jetzt ohne Umwege geht.** Die erste Vermutung
  — fehlende Qt-Plugins im Paket — ist **widerlegt**: PyInstaller sammelt
  `platforminputcontexts` und die drei `wayland-*`-Gruppen nachweislich mit
  (`_modules_info.py`). Was fehlte, war die Auskunft; der nächste Bericht
  nennt `xdg_session_type`, `qt_qpa_platform` und `qt_im_module`. Auch hier
  entscheidet erst eine Rückmeldung.

**Die Lehre ueber allen sechs:** Drei der Fehler waren Zusagen, die auf einer
Plattform galten und auf einer anderen nicht, und zwei waren Pruefungen, die
dieselbe Annahme benutzten wie ihr Prueflung. Kein einziger davon war eine
falsche Rechnung.


### Die Nachsuche im selben Gebiet (27.08.2026)

Robert: „schau erst nochmal gründlicher nach mehr fehler in dem Bereich".
Acht weitere, und der erste wiegt schwerer als alle sechs des Berichts
zusammen — er stand in der Behebung selbst.

- [x] **Vier Startpfade endeten weiter im Sandkasten** (`ca18e5a8`).
  `discover.on_host` gab es seit dem Vormittag, gerufen hat es nur die
  Slicer-Übergabe. Ollama, die Paketmanager und der ComfyUI-Lauf starteten
  weiter darin, wo es das Programm nicht gibt.

- [x] **Und eine Ebene tiefer half der Fix nichts** (`ca18e5a8`).
  `install_root` sucht die Cura-Definition mit `is_dir()`, und das sagt auf
  einen Host-Pfad zuverlässig nein. Ohne `-j <definition>` startet CuraEngine
  gar nicht: **Die Übergabe war auch nach dem Start-Fix noch tot, nur eine
  Ebene später.**

- [x] **AppImages wurden nie gefunden** (`ca18e5a8`) — der häufigste
  Linux-Fall. PrusaSlicer, OrcaSlicer, Cura und BambuStudio liefern dort in
  erster Linie eine einzelne Datei mit Version im Namen aus; alle fünf
  Suchstufen davor suchen einen exakten Namen in einem Installationsordner.

- [x] **macOS fand nie ein Slicer-Profil** (`ca18e5a8`). `XDG_CONFIG_HOME`
  setzt dort niemand.

- [x] **Die ComfyUI-Rateorte waren drei Laufwerkspfade** (`ca18e5a8`). Auf
  Linux ist `Path("F:/AI/...")` ein relativer Pfad namens „F:".

- [x] **Der Über-Dialog zeigte im Paket nie eine Fremdlizenz** (`07858c4e`).
  `runtime_packages` fragt die **eigene** Distribution, und die gibt es in
  keinem PyInstaller-Bau. PySide6 steht unter LGPL, §36 verlangt die Liste,
  und die Datei, die sie enthält, reiste die ganze Zeit mit — gelesen hat sie
  niemand.

- [x] **Die Zeigergröße galt nur für Linux** (`93128dc6`). Die Behebung des
  Berichts blieb auf halbem Weg stehen: Windows führt `CursorBaseSize` in der
  Registry, macOS einen Faktor in der Bedienungshilfe.

- [x] **Die Frage an das eigene Ollama ging an den Firmenproxy**
  (`22937d42`). `proxy_bypass("localhost:11434")` ist `False` — gemessen. Das
  Ergebnis wäre „Backend nicht erreichbar" für ein Programm, das läuft.

- [x] **Zwei Sandkästen brauchen einen Ort, der in keinem liegt**
  (`8c38d193`). Läuft Solidon selbst als Flatpak, ist sein Nutzer-Cache
  `~/.var/app/<id>/cache`, und `--filesystem=home` nimmt `~/.var` aus.

- [ ] **Ob die Übergabe an den Slicer im Flatpak jetzt ankommt.** Vier
  Startpfade, die Suche nach der Cura-Definition und der Austauschordner sind
  repariert (`ca18e5a8`, `8c38d193`), und jeder Schritt ist einzeln geprüft.
  **Die Kette als Ganzes nicht** — dazu braucht es zwei echte Flatpaks, und
  von Windows aus ist sie nicht messbar. Das ist der Punkt, an dem eine
  Rückmeldung mehr wert wäre als jede weitere Durchsicht hier.

**Die Lehre über allen, und sie ist eine andere als die des Berichts:**

> **Ein Modul, das eine Falle richtig benennt, ist gegen sie nicht immun.**

`discover.py` beschrieb die Flatpak-Falle für *fremde* Programme über
zwanzig Zeilen genau — und zählte sich selbst nicht mit. `find_program`
schrieb in seinen Docstring, eine falsche Auskunft sei teurer als keine, und
meldete zwanzig Zeilen später einen eingetragenen Host-Pfad als
verschwunden. `workspace_for` verhinderte den Fall „der Slicer sieht unser
`/tmp` nicht" und lief in „der Slicer sieht unser `~/.var` nicht".

Der Satz liest sich als Beleg, dass jemand nachgedacht hat — und **genau
deshalb prüft die Stelle niemand ein zweites Mal.**

**Und zweimal an einem Tag dieselbe Sache an Stellen, die nichts miteinander
zu tun zu haben schienen:** Im Flatpak gilt die XDG-Variable nicht, gemeint
ist der Rechner. Einmal für die Slicer-Profile, einmal für den
Austauschordner.

**Vier von fünf Gegenproben haben Tests bestätigt, eine hat einen Test
verworfen** — und zwar meinen eigenen vom selben Vormittag: Er sicherte zu,
dass der Arbeitsordner im `user_cache_dir()` liegt, also einen Ort statt der
Sache, und hätte damit den Fehler festgeschrieben, den er verhindern sollte.

### Was der Paketbau sonst noch anders macht (27.08.2026)

Ein Agent hat Entwicklung gegen Bau gemessen — 15 Datenpfade, 6
Metadaten-Aufrufstellen, 5 `sys.frozen`-Zweige, die 22 Bootstrap-Importe
gegen 160 eingesammelte Module. Kein Fund, der das Programm am Starten
hindert; die drei behobenen stehen oben und hier.

- [x] **`trimesh` bekäme im nächsten Bericht wieder einen Strich**
  (`07858c4e`). `trimesh.__version__` **ist** ein Metadatenaufruf und liefert
  ohne `.dist-info` `None` — die Behebung „erst das Modul" trägt für vier der
  sechs Pakete, für dieses nicht.

- [x] **Die Begründung dafür stand an drei Stellen und war falsch**
  (`07858c4e`). „`collect_data_files` nimmt die Metadaten nebenbei mit" —
  nachgemessen: 24 Einträge für `trimesh`, 495 für `numpy`, davon **null**
  mit `dist-info`. `numpy` steht im Bericht, weil es sein `__version__`
  wirklich selbst trägt: ein richtiges Ergebnis mit falscher Begründung.

- [x] **`pip install pyinstaller` war die einzige ungepinnte Installation**
  (`07858c4e`), während `constraints.txt` `pyinstaller==6.22.2` festnagelt.
  Gerade dessen Hooks entscheiden, was an Metadaten mitreist.

- [ ] **CA-Zertifikate auf macOS — Rückfall gebaut, Paketbestätigung offen.**
  Auf Windows liest CPython den Systemspeicher, auf Linux `/etc/ssl/certs`;
  auf macOS zeigen OpenSSLs Vorgabepfade in die Python-Installation des
  **Bauservers**, und die reist nicht mit. `app/core/network.py` setzt deshalb
  im gebauten macOS-Prozess vor dem ersten Netzzugriff `SSL_CERT_FILE` auf den
  mitgelieferten Mozilla-CA-Satz von `certifi`; eine ausdrücklich gesetzte
  Firmen-CA gewinnt. Die Spec sammelt die Datendatei ausdrücklich ein,
  Abhängigkeit, feste Version und MPL-2.0-Hinweis standen bereits im Baum und
  sind jetzt auch als Laufzeitvertrag festgehalten. Drei Tests decken Paket,
  Entwicklungsumgebung und Firmenvorgabe. Was von Windows aus nicht geht:
  ein echtes `.pkg` starten und *Hilfe → Nach Updates suchen* drücken.

- [x] **Zwei Prüfungen halten weniger, als ihr Name sagt — geschlossen am
  28.08.2026.**
  `test_packaging.py:82` steht auf „Was nur in einer Funktion importiert
  wird, sieht PyInstaller nicht" — gemessen falsch, `modulegraph` findet
  Funktionsimporte. Schaden richtet es heute nicht an (die zwölf gelisteten
  OCP-Module sind Redundanz), aber die Begründung schickt den nächsten Leser
  in die falsche Richtung. Und `test_packaging.py:70` durchsucht nur `app/`
  und vergleicht gegen das *Vorkommen einer Zeichenkette* in der Spec statt
  gegen das Ziel im Bau: `changelog/` liegt außerhalb und wird nie gesehen.

  Beide Prüfungen lesen jetzt die echte Python-Struktur der Spec: die
  Zielwerte der `datas`-Tupel und die festen Einträge der `hiddenimports`-
  Liste. Die Datensuche bildet sowohl `app/` als auch das außerhalb liegende
  `changelog/` auf ihren Paketpfad ab; Kommentare können keinen Vertrag mehr
  versehentlich erfüllen. Die falsche Begründung zu Funktionsimporten ist in
  Test und Spec berichtigt.

## Der Skizzenmodus für Anwender ohne CAD-Kenntnis (27.08.2026)

Robert, nach fünf Bildschirmfotos aus dem Skizzenmodus: „so ganz passt das
bei zeichnen mit der vorderansicht, draufsicht und seitenansicht aber noch
nicht, schön wäre auch dass wenn ich in der skizze was in der draufsicht
zeichne und dann in die Seitenansicht oder vorderansicht gehe sie nach oben
ziehen kann." Und danach: „mach den skizzenmodus perfekt zum leicht zeichnen
für anwender ohne große cad kenntnisse — modelle erzeugen und ändern,
erstellen, ausschneiden usw, vergleiche cad software dafür zb fusion."

**Zwei Befunde sind behoben, und beide waren älter als die Frage.**

- [x] **Die Zeichnung kippte beim Ebenenwechsel mit** (`8e8699f6`). Die
      2D-Zahlen blieben, der Ort im Raum wanderte: ein Punkt bei (10 | 5) lag
      in der Draufsicht bei (10, 5, 0), in der Vorderansicht bei (10, 0, 5).
      Weil die Kamera mitschwenkt, sah **jede** Ansicht gleich aus — genau
      das, was Robert schon am 24.08. gemeldet hatte („bei draufsicht,
      seitenansicht usw sieht man auch keinen unterschied") und was damals als
      Kamerafrage behoben galt. Jetzt nagelt der erste Strich die Ebene fest;
      danach dreht die Wahl nur noch die Ansicht, und ein Satz daneben sagt
      es.
- [x] **Wer einen Körper erzeugte, sah beim Tippen nichts** (`5ccdfbaf`).
      `compare_scenes` übersprang Objekte ohne Vorgänger, also stand ein neuer
      Körper allein in `created` — die Ansicht zeichnet `entries`. Gemessen an
      einer Extrusion: 0 statt 1 Eintrag, 0 statt 9600 mm³. Betraf **jede**
      erzeugende Operation, also den Anfang von Weg 2.

**Was schon gemessen ist und nicht wiederholt werden muss:**

| Frage | Antwort |
|---|---|
| Fehlt Funktionsumfang? | Nein. `sketch_extrude`, `sketch_pocket`, `sketch_revolve`, `sketch_sweep`, `sketch_loft`, dazu `fillet_edges`, `chamfer_edges`, `mirror_object`, `pattern`, `shell_exact`. Es fehlt der **Weg** dorthin, nicht die Rechnung |
| Trägt eine Live-Vorschau? | Ja. Eine Extrusion kostet warm **1,1 bis 1,8 ms** (kalt 461 ms, OCC-Import) — gegen 16 ms Budget bei sechzig Bildern |
| Wie kommt man heute zur Operation? | „Fertig" → `SketchUseDialog` mit fünf Arten → `run_operation`. Der Gedanke stimmt schon: gefragt wird **nach** dem Zeichnen, mit der Zeichnung vor Augen |
| Wie läuft die Vorschau? | `dialog.valuesChanged` → 300-ms-Timer → `session.preview_async` → `show_difference`. Die 300 ms sind für teure Operationen da |

**Die damals offenen Grundlagen sind gebaut; die anschließenden
Fusion-Befunde sind unten ebenfalls umgesetzt und geprüft.**

- [x] **Der Ziehgriff zieht jetzt.** In der Querschau — Blick und Zeichenebene
      auseinander, also genau dort, wo man ohnehin nicht zeichnen kann — wird
      aus einem Zug am Umriss eine Höhe. `axis_hit` (Kern) rechnet aus dem
      Sichtstrahl die Stelle der größten Annäherung an die Aufzugsachse durch
      den gegriffenen Punkt; `pull_cage` legt die Drahtform in die Szene, die
      dabei wächst; `DragValueBar` zeigt die Zahl **am Zeiger** und nimmt eine
      getippte an; beim Loslassen geht `sketch_extrude` mit Skizze **und** Höhe
      auf. Gefahren wird das über denselben Rückruf wie der Körperzug
      (`on_body_drag`, vier Schritte) — eine zweite Klickschwelle daneben war
      der Fehler, den der Körperzug schon einmal hatte.

      Drei Entscheidungen dabei, die man sonst nachfragen müsste. Der Griff ist
      **der Umriss selbst**, gemessen in Bildpunkten gegen seine projizierten
      Strecken und so weit reichend wie die Fangmarke groß ist — was man sieht,
      kann man greifen. Angeboten wird er über einen **Zustand** (Querschau)
      und nicht über ein Winkelmaß: Zwei Schwellen für dieselbe Frage lassen
      immer einen Bereich, in dem beide Antworten falsch sind. Und die Grenzen
      der Höhe kommen **aus dem Schema** der Operation, damit die Zahl am
      Zeiger dieselbe ist, die der Dialog danach annimmt.
- [x] **Die Zahl hat jetzt einen Satz daneben** (`outline_advice`). Drei Lagen,
      drei Folgen: „Erst ein geschlossener Umriss wird ein Körper" — „Daraus
      wird ein Körper; Maße legen fest, was nicht mehr wackeln soll" — „Daraus
      wird ein Körper, und die Form kann nicht mehr wackeln." Die Zahl bleibt
      stehen, denn für den Könner ist sie richtig. Dieselbe Behandlung haben
      die zehn Bedingungsknöpfe bekommen: `_does_phrase` sagt, was eine
      Bedingung **bewirkt** („legt eine Linie glatt an einen Kreis oder Bogen
      an"), und steht am Knopf, im Kontextmenü, in der Meldung nach einem
      Kürzel und an jedem Eintrag der Bedingungsliste — vier Stellen, eine
      Quelle. `_needs_phrase` sagte bis dahin nur, was ausgewählt sein muss;
      das ist die Bedienung und nicht die Sache.

**Die Klickmessung, Solidon-Spalte** — gemessen am gebauten Fenster
(27.08.2026), jeder Schritt wirklich ausgeführt bis zum Ergebnis:

| Aufgabe | Solidon | Fusion |
|---|---|---|
| Rechteck 40 × 20, bemaßt | **3** — Zeichnen, Grundform, Rechteck 40 × 20 | **4** + Tippen — Skizze erstellen, Ebene, Rechteck, erste Ecke, dann 20 Tab 40 Enter |
| Rechteck extrudieren, über den Dialog | **6** — dazu Fertig, Weiter, Übernehmen | **7** — dazu Skizze fertig stellen, Extrusion, OK |
| Rechteck extrudieren, über den Ziehgriff | **6** — dazu Ebenenwahl, Ziehen, Übernehmen | nicht gemessen — Fusion hat den Pfeil **im** Dialog, nicht daneben |
| Tasche schneiden (auf einem exakten Körper) | **9** — Körper, Fläche, Zeichnen, Grundform, Rechteck, Fertig, *Tasche* wählen, Weiter, Übernehmen | **9** — Skizze erstellen, Deckfläche, Rechteck, zwei Ecken, Fertig stellen, Extrusion, Profil, OK |
| Verrunden | **4** — Körper, Ändern, Verrunden, Übernehmen | **3** — Kante, Verrundung, OK |
| Vom Start zur leeren Szene | **0** — die Anwendung öffnet mit einer | **2** — Neue Konstruktion, Neu erstellen |

**Die Zahlen sind erstaunlich nah beieinander, und das ist der eigentliche
Befund.** Solidon ist bei drei Aufgaben gleich schnell oder schneller und bei
einer langsamer. Wer gehofft hatte, der Abstand liege in der Zahl der Klicks,
findet ihn dort nicht — er liegt darin, **was zwischen den Klicks passiert.**

Zwei Einschränkungen, damit die Tabelle nicht besser aussieht, als sie ist.
Solidons Rechteck ist ein **festes** 40 × 20 aus dem Menü; Fusions vier Klicks
ergeben *jedes* Maß, und wer bei uns 35 × 18 will, geht einen längeren Weg, der
hier nicht gemessen ist. Und der eine Klick, mit dem ich in Fusion ein Wertfeld
nachträglich anklicken musste, ist meiner Fernsteuerung geschuldet und zählt
nicht: Am Platz tippt man direkt, das Feld hat den Fokus.

**Der Ziehgriff spart dabei keinen einzigen Klick**, und das ist die
überraschendste Zahl der Messung: sechs gegen sechs. Was er einbringt, ist
nicht der kürzere Weg, sondern dass die Höhe **gesehen** statt geraten wird —
wer 15 mm zieht, hat keine Zahl getippt und trotzdem eine. Wer den Weg kürzen
will, sieht die Messung anders an: Von den fünf Aufgaben tragen `sketch_extrude`,
`sketch_pocket` und `fillet_edges` **kein Kürzel**, und bei der Tasche kosten
zwei der neun Klicks allein die Frage „Was soll daraus werden?", in der die
Tasche an vierter Stelle steht.

Die folgende Vergleichsmessung lieferte die nächste, inzwischen gebaute
Ausbaustufe:


### Was Fusion besser macht — am laufenden Programm gesehen (27.08.2026)

Robert, nach dem Messlauf: „fusion finde ich relativ einfach, schön und
übersichtlich, ebenso leicht zu verstehen, evtl können wir davon einiges
übernehmen" — und dazu die Beobachtung, auf die alles hinausläuft: „**vor allem
auch schon alles ab klick 1**". Der Maßstab dahinter, in seinen Worten: „ziel
solidon, wenig cad kenntnisse, einfach, leicht, verständlich, modernes schickes
design".

Neun Beobachtungen, jede beim Fahren der vier Aufgaben gesehen und nicht aus
dem Gedächtnis geschrieben. Die Bildschirmfotos dazu liegen nicht im
Repository; was zählt, steht hier.

**1. Ab Klick 1 steht etwas im Bild, das man anfassen kann.** Ein Klick auf
*Skizze erstellen*, und die drei Ursprungsebenen liegen als greifbare Flächen
in der Szene — man klickt die an, auf die man zeichnen will. Solidon liest die
Ebene aus einem Auswahlfeld („Draufsicht (XY)"). Das Feld ist genauer, die
Flächen sind verständlicher, und für „wenig CAD-Kenntnisse" gewinnt das Bild.

**2. Jeder Werkzeughinweis nennt die Bedienfolge.** Dreiteilig: Name mit
Kürzel, ein Satz was es tut, dann *wie es geht* — „Wählen Sie den ersten Punkt
als Anfang des Rechtecks aus. Wählen Sie den zweiten Punkt aus, oder geben Sie
die Werte für Höhe und Breite an." Dazu „Strg+/ für weitere Hilfe". Wir haben
genau diese Form gerade für die zehn Bedingungsknöpfe gebaut (`_does_phrase`);
Fusion hat sie an **jedem** Werkzeug.

**3. Zwei Maße hängen gleichzeitig am Zeiger, mit Schloss.** Beim Rechteck
stehen Breite und Höhe zusammen da, Tab wechselt zwischen ihnen, und ein
Schloss-Symbol zeigt, welche Zahl schon festgenagelt ist. Unser Maßfeld (E19)
nimmt eine Zahl und weiß von der zweiten nichts.

**4. Was eindeutig ist, wird nicht gefragt.** Beim Extrudieren einer Skizze mit
genau einem Umriss stand das Profil schon im Dialog, und unten rechts las man
„1 Profil | Bereich: 800,00 mm²". Solidon fragt „Was soll daraus werden?" auch
dann, wenn es nur eine sinnvolle Antwort gibt — zwei Klicks für eine Auskunft,
die die Anwendung hat. **Und bei der Tasche kehrt sich das um:** Dort hat die
Skizze auf der Fläche zwei Gebiete, Fusion fragt zu Recht, und der Klick auf das
Profil ist derselbe wie unser Klick auf *Tasche schneiden*.

**5. Die Operation folgt der Geste, nicht einer Liste.** Ich habe die Tiefe der
Tasche als **−5** eingetippt, und Fusion stellte *Vorgang* selbst auf
„Ausschneiden". Man wählt nicht zwischen Extrudieren und Tasche schneiden, man
zieht in die eine oder die andere Richtung. **Das ist die stärkste Übernahme für
den Ziehgriff, den wir heute gebaut haben:** Wir sagen dort „Der Körper wächst
von der Zeichenebene weg — andersherum ziehen", wo ein Zug **in** den Körper
`sketch_pocket` sein könnte. Aus einer Absage würde eine zweite Operation.

**6. Die Zahl steht zweimal, und das ist kein Widerspruch.** Beim Verrunden
hängt ein Ziehgriff mit Wertfeld an der Kante **und** die Zeile „1 Kante |
0,00 mm" im Dialog. Kein Entweder-oder zwischen „am Zeiger" und „im Dialog" —
beides, und die eine Zahl.

**7. Der Griff ist zu sehen, bevor man ihn sucht.** Der Extrusionsdialog legt
einen blauen Pfeil in die Mitte des Profils. Unser Ziehgriff **ist** der Umriss
und damit unsichtbar, bis der Zeiger darüber steht; der Satz in der Leiste
(„Am Umriss ziehen zieht daraus einen Körper auf") ist ein Ersatz für ein
Zeichen im Bild, und Text ist der schlechtere Weg zu einer Geste.

**8. Die Auswahl wird quittiert, ohne dass man fragt.** Unten rechts stand
durchgehend, was gewählt ist, in Sachbegriffen und mit Zahl. Wir haben die
Auskunft im Objektbaum und in der Statusleiste, aber nicht als ruhige Zeile am
Bildrand.

**9. Der Modus hat eine eigene Palette.** Rechts stand die SKIZZENPALETTE mit
allem, was im Skizzenmodus schaltbar ist — Fang, Skizzierraster, Bemaßungen,
Abhängigkeiten, Punkte, Profil, Konstruktionsgeometrie —, jedes als Haken.
Unsere Entsprechungen liegen in der Werkzeugzeile, teils gar nicht, und die
Zeile ist der breiteste Posten des Modus.

**Was daran nicht übernommen werden sollte**, damit die Liste eine Liste bleibt
und kein Auftrag: Fusion braucht zwei Klicks und einen Dialog, bevor eine leere
Szene dasteht, und es verlangt eine Kontoanmeldung, bevor überhaupt etwas geht.
Beides ist genau das, was §2.3 („die ersten fünf Minuten") und §2 („ohne Konto
benutzbar") ausschließen.

Gebaut und geprüft daraus:

- [x] **Der Ziehgriff braucht ein Zeichen im Bild.** Ein Pfeil (oder eine
      Marke) auf dem Umriss, damit die Geste ohne Satz gefunden wird; der Satz
      in der Leiste ist eine Beschreibung und keine Affordanz im Bild.

      **Und das Zeichen muss sagen, wohin.** Ein Pfeil in der Bildebene kann
      eine Richtung senkrecht dazu nicht zeigen — dafür hat das Projekt längst
      eine Konvention, und sie steht weiter oben im Register: **Punkt** heißt
      „kommt heraus", **Kreuz** heißt „geht hinein" (Achsansichten, dieselbe
      Datei). In der Querschau liegt die Aufzugsachse **in** der Bildebene,
      dort trägt ein Pfeil; in jeder anderen Lage ist der Griff heute gar nicht
      angeboten, und der Entwurf muss sagen, was das Zeichen dort tut, wenn er
      die Lage öffnet. Das ist Bedienlogik vor Code (Einordnung der
      Review-Sitzung, 27.08.2026).

      **Gebaut am 28.08.2026:** `pull_handle` setzt Pfeil und Kreuz an den
      längsten Profilabschnitt und hält ihre Länge mit **38 Bildpunkten** bei
      jedem Zoom konstant. Die manuelle Trefferprüfung umfasst Schaft,
      Pfeilspitze und Kreuz vollständig — was sichtbar ist, ist greifbar.
      Wortpaar und unterschiedliche Zeichen kodieren die Bedeutung zusätzlich
      zur Farbe (Regel 18).
- [x] **Ein Zug in den Körper könnte `sketch_pocket` sein statt einer Absage.**
      Fusion stellt *Vorgang* selbst auf „Ausschneiden", sobald die Tiefe
      negativ wird; wir sagen dort „andersherum ziehen". Aus der Absage würde
      eine zweite Operation — die stärkere Übernahme, und die mit zwei Haken,
      die vor der Umsetzung gehören:

      * **Regel 21 verbietet den stillen Wechsel.** Fusion tauscht den Vorgang
        **sichtbar** im Dialog; ein Operationswechsel mitten in der Geste, den
        niemand ankündigt, wäre Raten über die Absicht. Es braucht eine
        deutliche Anzeige mit zweiter Kodierung (Regel 18) — etwa die
        Drahtform, die nach innen statt nach außen wächst, **und** ein
        Wortwechsel an der Wertleiste.
      * **Die Absage bleibt als Rückfall.** Es gibt vier gemessene Fälle, in
        denen `sketch_pocket` das Volumen unverändert lässt (weiter oben in
        dieser Datei, „Die Tasche schnitt daneben"); wo unter der Ebene nichts
        zu schneiden ist, muss der Zug weiter eine Auskunft geben. Die
        B5-Meldung wird ergänzt, nicht ersetzt.

      **Gebaut am 28.08.2026:** Die gezogene Zahl behält ihr Vorzeichen bis
      zur Bedienentscheidung. Nach außen steht *Höhe* und führt zu
      `sketch_extrude`, nach innen steht *Tiefe* und führt sichtbar in den
      Dialog von `sketch_pocket`. Der Innenzug ist nur bei genau einem
      ausgewählten B-Rep-Körper zulässig; ohne Körper oder bei einem Netz
      bleibt die Skizze offen, ein Handlungssatz erscheint und Drahtkäfig wie
      Wertanzeige verschwinden vollständig. Beide Zahlenbereiche kommen aus
      den jeweiligen Operationsschemata.
- [x] **Auch bei einem Umriss bleibt die Erzeugungsart eine sichtbare
      Entscheidung.** Ein geschlossenes Profil kann aufgezogen, gedreht oder
      entlang eines Pfads geführt werden; eine automatische Extrusion wäre
      damit stilles Raten über die Absicht (Regel 21). Die Anfängerhilfe liegt
      in einer klaren Vorwahl statt in einem versteckten Operationswechsel.

      **Gebaut und nach Review korrigiert am 28.08.2026:** `SketchUseDialog`
      zeigt alle fünf registrierten Wege mit Beschreibung. *Aufziehen* steht
      als verständlicher Normalfall oben und ist markiert, sodass die
      Eingabetaste genügt; die Entscheidung bleibt trotzdem sichtbar und
      änderbar. *Zurück zum Zeichnen* öffnet den Editor mit exakt derselben
      Zeichnung. Ein Regressionstest fährt ausdrücklich den Fall „eine Region,
      leere Szene" und hält Vorwahl, fünf sichtbare Wege und verlustfreien
      Rückweg zusammen fest.
- [x] **Vier Kleinere, jedes für sich klein.** Die Ebenen als anfassbare
      Flächen im Bild statt (nur) im Auswahlfeld; zwei Maße in einer Tab-Kette
      mit Schloss statt eines Feldes; die Bedienfolge in **jedem**
      Werkzeughinweis statt nur an den Bedingungsknöpfen; und die ruhige Zeile
      am Bildrand, die sagt, was gewählt ist. Zusammen sind sie das, was Robert
      „alles ab Klick 1" genannt hat.

      **Gebaut am 28.08.2026:** Beim freien Start stehen drei moderne,
      tastaturbedienbare Ebenenkarten mitten im Bild; auch die bereits
      vorausgewählte Draufsicht schließt die Frage sauber. *Rechteck* ist ein
      echtes Zwei-Klick-Werkzeug mit Breite und Höhe, Tab-Reihenfolge und je
      einem sichtbaren Schloss; gefangene Ecken werden im selben
      Rückgängig-Schritt als Deckung gespeichert. Jeder Zeichenknopf nennt
      Name, Kürzel und erste Klickfolge. Eine wortbasierte Auswahlquittung
      steht ruhig am unteren Bildrand, und während des Zeichnens verschwindet
      die allgemeine Werkzeugleiste zugunsten des klar benannten
      Skizzenbands.

      Die Abnahme deckt insbesondere die sechs Review-Rückfälle ab:
      sichtbare Fünf-Wege-Vorwahl mit verlustfreiem Rückweg, gesamte Griff-Trefferfläche,
      Vorschau-Aufräumen bei beiden Innenzug-Absagen, Rechteckfang,
      Ebenenwahl auf dem bereits aktiven Eintrag sowie gemeinsames Ausblenden
      beider Maßfelder und Schlösser.


### Die obere Bedienzone: drei Bänder, wo der Bauplan eines zeichnet (27.08.2026)

Robert, nach dem Fusion-Lauf: „auch mit weniger klicks finde ich fusion in
manchen punkten noch übersichtlicher, vor allem durch das ribbon menü oben, wir
wollen alles perfekt und innovativ für anwender ohne cad kenntnisse."

**Gemessen am gebauten Fenster**, weil der Eindruck sonst gegen einen Eindruck
steht:

| | Solidon heute | Fusion |
|---|---|---|
| Bänder über der Ansicht | **drei** — Menüleiste, obere Werkzeugleiste, Werkzeugzeile | **eines** |
| Menüs / Reiter | 9 Menüs, 71 Zeilen zusammen | 7 Reiter, dazu ein Kontextreiter (*Skizze*) |
| davon Untermenüs | **20** | keine |
| Tiefe bis zu einer Erzeugungs-Operation | **3 Klicks** — *Erzeugen* besteht aus 4 Zeilen, und alle 4 sind Untermenüs | **1 Klick**, sobald der Reiter steht |
| Tiefe bis zu einer Änderungs-Operation | **3 Klicks** — *Ändern*: 7 Zeilen, alle 7 Untermenüs | **1 Klick** |
| Gruppennamen | erst beim Aufklappen zu sehen | **immer sichtbar** (ERSTELLEN, ÄNDERN, PRÜFEN …) |
| Operationen im Register | 91 in 15 Kategorien, 14 mit Kürzel | — |
| Symbole gleichzeitig im Band | 7 Umschalter unter der Ansicht | rund 30, **keines mit Wort** |

**Das ist der Kern, und er ist nicht Geschmack:** Bei uns liegt jede Operation
zum Erzeugen und Ändern **drei** Klicks tief, und wie die Gruppe heißt, erfährt
man erst, wenn man aufklappt. Bei Fusion ist es einer, und die Verben stehen
dauernd da. Genau das meint „schon alles ab Klick 1".

**Was der Bauplan dazu sagt — und er sagt mehr, als erwartet.** §2.5 zeichnet
**eine** Werkzeugleiste über den drei Zonen, nicht drei Bänder; wir haben drei.
Das ist ein Fund und keine Auslegung. Gleichzeitig schließt §2.5 ausdrücklich
aus, was Fusions Reiter sind: „Keine Betriebsarten, keine Umschaltung zwischen
‚Bearbeiten' und ‚Konstruieren'" — und `AGENTS.md` führt
„Betriebsarten-Umschaltung in der Oberfläche" unter *Was NICHT gebaut wird*.
Fusions fünf Arbeitsbereichs-Reiter (Volumenkörper, Fläche, Netz, Blech,
Kunststoff) sind damit **kein** Vorbild; sein **Kontextreiter** (*Skizze*
erscheint im Skizzenmodus und verschwindet mit ihm) ist keine Betriebsart,
sondern folgt dem Zustand — und der ist nach §2.5 die Szene.

Dazu §2.6: Entdeckbarkeit läuft über Befehlspalette, Kontextmenü am Merkmal und
Bausteinkatalog mit Bildern. Ein Band ist dort nicht genannt, aber auch nicht
ausgeschlossen.

**Und Fusions Band hat für unsere Zielgruppe eine harte Schwäche:** rund dreißig
Symbole gleichzeitig, **keines mit einem Wort**. Wer die Symbole nicht kennt,
muss jedes einzeln überfahren. Für „wenig CAD-Kenntnisse" ist das die falsche
Hälfte des Vorbilds — übersichtlich ist dort die **Struktur** (ein Band,
benannte Gruppen, eine Ebene), nicht die Dichte.

Drei Wege, mit Kosten. Keiner ist gebaut, und keiner sollte ohne Entscheidung
gebaut werden — §2.5 legt das Fensterschema fest, und
`tests/test_interface_limits.py` kodiert die Zahlen.

**Nachtrag am 27.08.2026: Ein Stück von A war kein Umbau, sondern ein
Fehler.** Die Regel „gefaltet wird, weil es sein muss, nicht weil es ordentlich
aussieht" stand seit dem 24.08.2026 fest und war für das **Kontextmenü**
geprüft. Die Menüleiste hatte sie nie bekommen — und schlimmer: Ihre Zählung
(`group_is_flat`) zählte Einträge mit, die das Menü nie zeigt. *Erzeugen* zeigt
**11** Zeilen, gezählt wurden **14**, die Grenze liegt bei zwölf. Die drei
Fehlenden sind die übrigen Mitglieder der Variantengruppe, die unter einem
Sammeleintrag stehen.

Gebaut ist deshalb:

- [x] **`menu_rows_of` zählt, was zu sehen ist**, und `group_is_flat` fragt
      sie. *Erzeugen* ist damit flach: **drei Klicks sind zwei geworden**, für
      jede Erzeugungs-Operation, im Menü, das Weg 2 trägt.
- [x] **Der Gruppenname bleibt sichtbar, auch flach** (`addSection` statt
      `addSeparator`). Vorher hielt ein nackter Trennstrich die Kategorien
      auseinander und benannte sie nicht; man erfuhr den Namen nur, wenn ein
      Untermenü ihn trug — also genau dann, wenn der Weg einen Klick länger
      war. Das ist die Fusion-Eigenschaft, die Robert genannt hat, und sie
      kostet keine Zeile: Eine Überschrift ist ein Trennstrich mit Text und
      zählt in der Grenze nicht mit. Bei einer einzigen Kategorie bleibt sie
      weg, sonst hieße sie wie das Menü darüber.
- [x] **Vier Tests dazu**, drei davon mit Mutationsprobe gegen die alte
      Zählung (alle drei fallen). Der vierte ist die Menüleisten-Fassung des
      Kontextmenü-Tests, die fehlte.

Gemessen danach: *Erzeugen* 11 Zeilen ohne Untermenü mit vier Überschriften,
*Vorbereiten* 10 mit zwei, *Objekt* und *Bausteine* ohne überflüssige
Überschrift. `menu_path` folgt von selbst — „Erzeugen → Quader anlegen" statt
„Erzeugen → Grundformen → Quader anlegen" —, weil Handbuch, Agent und Leiste
dieselbe Funktion fragen.

**Zweiter Nachtrag, 27.08.2026: Für *Ändern* war Flachziehen auch nicht die
Antwort — aber „alles falten" war sie noch weniger.** Der Absatz darüber stellte
die Frage falsch: Ein Menü mit 33 flachen Zeilen muss falten, aber nicht
**alles**. Die Regel dafür stand seit dem 24.08.2026 fest und war für das
Kontextmenü gebaut — `folded_groups` faltet nur so weit, bis der Rest passt. Die
Menüleiste hatte sie nicht, und sie konnte sie nicht haben: Die Rechnung lag in
`app/ui/panels.py`, und `menu_path` (Kern) darf von dort nicht lesen (§8). Also
hatte der Kern ein zweites, gröberes Modell — alles flach oder jede Kategorie
eine Ebene tiefer.

Gebaut:

- [x] **`folded_groups` und `menu_rank` sind in den Kern gezogen**
      (`app/core/registry/surfaces.py`). Wörtlich übertragen, um einen
      `rank`-Parameter erweitert: das Kontextmenü ordnet nach der Menüleiste,
      die Leiste nach der Stellung der Kategorie in `MENU_GROUPS`. Zwei
      Ordnungen, **eine** Rechnung.
- [x] **`folded_categories(kategorie)`** ist die neue Antwort, und `menu_path`
      wie `_build_menus` fragen sie. `group_is_flat` bleibt als dünner Aufrufer
      darüber — die Frage „kommt die Gruppe *ganz* ohne Zwischenebene aus"
      kommt weiter vor, sie rechnet nur nicht mehr selbst.
- [x] **Ein Fehler im Ausweichzweig von `folded_groups` mitgefunden.** Er
      fragte den Rang nur dort, wo eine einzelne Gruppe schon genügt; wo die
      großen zuerst fallen müssen, entschied bei Gleichstand der **Name**.
      Damit fiel im Menü *Ändern* „Verbinden und Abziehen" statt „Formgebung",
      weil `boolean` alphabetisch vor `shaping` steht — die häufigere Gruppe
      wanderte tiefer als die seltenere. Die Zusage „wer falten muss, faltet
      hinten" stand im Docstring und galt für die halbe Funktion.
- [x] **Drei Tests, alle drei mit Mutationsprobe** (jede fällt gegen den alten
      Stand): die Regel je Kategorie, der Gleichstand, und der **Anschluss** —
      der genannte Weg gegen den gebauten, am Fenster gemessen.

Gemessen danach, Menü *Ändern* bei einer Grenze von zwölf:

| Kategorie | Zeilen | vorher | nachher |
|---|---|---|---|
| Verbinden und Abziehen | 4 | Untermenü | **direkt** |
| Transformation | 9 | Untermenü | Untermenü |
| Formgebung | 4 | Untermenü | Untermenü |
| Bohrungen | 3 | Untermenü | **direkt** |
| Oberfläche | 3 | Untermenü | Untermenü |
| Netz | 9 | Untermenü | Untermenü |
| Reparatur | 1 | Untermenü | **direkt** |

Zusammen 12 Zeilen, genau an der Grenze. **Acht Operationen rücken von drei auf
zwei Klicks**: Vereinigen, Abziehen, Schnittmenge, Weich verschmelzen, Bohrung
setzen, Bohrung verschließen, Senken, Reparieren. Darunter die Bohrung — genau
der Eintrag, dessen zweiter Klick am 24.08.2026 den Umbau des Kontextmenüs
ausgelöst hat und der im Menü seither drei kostete.

**Der Anschlusstest hat dabei sich selbst widerlegt, und das gehört in die
Notiz.** Seine erste Fassung ordnete Menüeintrag und Operation über
`action.data()` zu. Von 158 Menüeinträgen tragen **sechs** ein `data`, und keiner
davon ist eine Operation — es sind die zwei Themen und die vier
Navigationsarten. Der Test sammelte diese sechs, verglich null Operationen und
blieb in der Mutationsprobe grün, während `menu_path` auf die alte Frage
zurückgesetzt war. Sein eigener Wächter (`assert gebaut`) fragte, ob das
Wörterbuch **voll** ist, nicht, ob Operationen darin stehen. Jetzt ordnet er
über den Titel zu und zählt: `assert verglichen >= 60`. Ein Wächter muss die
Größe messen, an der der Test scheitert.

**Was von A jetzt noch offen ist:** *Bausteine* (26 flach) und *Ansicht* (23).
Für beide bleibt die Antwort dieselbe wie oben — Katalog mit Bildern (§2.6)
beziehungsweise die Ansicht selbst, nicht ein Menü. Das ist B und C.

**Was von A offen bleibt**, und es ist der schwierigere Teil: *Ändern* (33
flach), *Bausteine* (26) und *Ansicht* (23) passen nicht in die Zwölf. Für sie
ist Flachziehen die falsche Antwort — die Bausteine gehören in den Katalog mit
Bildern (§2.6 sagt das ausdrücklich), die Ansicht in die Ansicht, und *Ändern*
bräuchte eine Aufteilung, die keine Zwischenebene ist. Das ist B und C.

**A — Nur die Tiefe kürzen, Schema unberührt.** Untermenüs auflösen, wo eine
Kategorie in die Zwölf-Zeilen-Grenze passt: *Erzeugen* und *Ändern* tragen
zusammen 11 Untermenüs, und die meisten Kategorien haben weniger als zwölf
Einträge (`parts` mit 26 ist die Ausnahme und bleibt ein Untermenü). Aus drei
Klicks werden zwei. **Kosten:** klein, ein Tag; berührt `test_interface_limits`,
das Handbuch (es verweist auf Menüwege) und die Tour. **Ändert nichts am
Bauplan.**

**B — Ein benanntes Band statt Menüleiste plus oberer Werkzeugleiste.** Was
§2.5 ohnehin zeichnet: **eine** Leiste, Gruppen nach Verben, und — anders als
Fusion — **mit Wörtern**, weil unsere Zielgruppe die Symbole nicht kennt. Ohne
Arbeitsbereichs-Reiter, mit einem Kontextabschnitt, der wie Fusions
*Skizze*-Reiter mit dem Zustand kommt und geht. **Kosten:** groß; berührt
Menüleiste, Kopfleiste, Werkzeugzeile, `test_interface_limits`, Handbuch, Tour
und jedes Bildschirmfoto. **Braucht einen Entwurf, bevor eine Zeile entsteht.**

**C — Das Band folgt der Auswahl.** Die innovative Variante, und die einzige,
die über Fusion hinausgeht: Fusions Band ist je Arbeitsbereich **statisch** — es
zeigt immer alles, auch was gerade nicht geht. Unser Register weiß es besser:
`applies_to` und `for_feature` beantworten schon heute, welche Operationen auf
das Gewählte passen (§2.6 nutzt das im Kontextmenü, die Palette sortiert
danach). Ein Band, das **vorn zeigt, was jetzt geht**, liest sich für einen
Anfänger nicht als 91 Operationen, sondern als die fünf, die zur Bohrung unter
dem Zeiger passen. **Kosten:** wie B, plus die Frage, die B nicht hat — ein
Band, dessen Inhalt sich ändert, kostet Wiederfinden („wo ist es hin?"). Der
Ausweg wäre ein fester Grundsatz plus eine wachsende Kontextgruppe, aber das ist
Entwurfsarbeit und keine Zeile Code.

**Meine Empfehlung, und die Entscheidung liegt bei Robert:** A ist unstrittig
und sofort machbar — reine Tiefenreduktion, kein Schemabruch, messbarer Gewinn
(drei Klicks auf zwei bei 47 der 91 Operationen). B und C gehören in **eine**
Konzeptarbeit, denn B allein wäre ein Fusion-Abklatsch mit unseren Wörtern, und
C ohne B hat keinen Ort. Was dabei ausdrücklich nicht übernommen wird: die
Arbeitsbereichs-Reiter (§2.5) und die wortlose Symboldichte.

Offen:

- [x] **Die Entscheidung über die obere Bedienzone — gefallen am 29.08.2026:
      Robert lehnt B und C ab.** Wörtlich „ich glaub ich will eher den
      aktuellen stand aber optimiert", nachdem ihm der Merge-Umfang des
      Bandes gezeigt worden war. Der Branch `codex/command-band-integration`
      wird nicht gemergt; `app/ui/command_band.py` und sein Test sind aus
      main entfernt (30.08.2026), das Konzept trägt den Stand „vorgelegt und
      abgelehnt". Was von der Messung bleibt, ist gebaut: Weg A, die
      Bausteine im Katalog statt im Menü, und *Ansicht* erwies sich als kein
      Befund — seine 21 tiefen Einträge sind Einstellungen, keine
      Operationen.

**Nachtrag am 28.08.2026 — die sichere Schicht davor ist gebaut.** Roberts
Auftrag „für Kunden ohne CAD-Kenntnisse einfach, schön und modern" lässt vier
Verbesserungen zu, ohne die offene Entscheidung B/C vorwegzunehmen:

- [x] **Die sieben Hauptknöpfe tragen Symbol und Wort.** *Zeichnen*, *Formen*
      und *Skelett* sind keine allgemein bekannten Piktogramme; ihr Name stand
      vorher erst am Mauszeiger. Die Zeile bleibt einzeilig und passt mit
      Projektname, Außenmaß, Drucker und Material bei 1280 Bildpunkten.
- [x] **Der erste Start hat eine Hierarchie.** Willkommen und kurzer Einstieg,
      dann *Grundlagen* für Sprache, Drucker und Material, danach klar als
      freiwillig bezeichnete *Optionale Erweiterungen*. Der Installationsknopf
      trägt nur noch seine Handlung; der Zustand steht als eigener Satz daneben.
- [x] **Installiert ist nicht mehr „fehlt".** Ein ruhendes Comfy Desktop wird
      als *installiert* gezeigt, ein antwortender Dienst als *bereit* und nur
      ein wirklich fehlender Weg als *nicht eingerichtet*.
- [x] **Die vier Startkacheln sprechen in Absichten.** Keine sichtbaren
      „Weg 1–4" und kein „Mesh" als Voraussetzung: *Vorhandenes Modell
      anpassen*, *Eigenes Teil bauen*, *Modell aus Text oder Bild vorbereiten*,
      *Figur frei formen*. Dateinamen und Abnahmepfade bleiben unverändert.

Das entscheidet B/C weiterhin nicht: Menüleiste und Werkzeugleiste werden
nicht zu einem neuen Band umgebaut. Es beseitigt aber die wortlose Dichte und
die falsche Erststart-Aussage, ohne das Fensterschema oder die 91 Operationen
zu verschieben.

---

## Linux durfte nicht updaten, und Windows fragte sechsmal (28.08.2026)

Robert hat zwei Dinge zusammen aufgetragen: den Ablauf des Updates glätten, und
**„mac und linux genauso wie windows, ohne weniger Funktionen"**. Der zweite Satz
traf eine Lücke, die keiner Plattform anzusehen war.

**Was gemessen war.** Ausgeliefert werden vier Pakete: `Setup-0.2.1.exe`, zwei
`.pkg` für macOS und `Solidon3D-0.2.1-x86_64.flatpak` (276 MB). Windows und
macOS standen in der Versionsdatei und ließen sich aus der Anwendung holen —
Linux nicht. Die Begründung stand als Kommentar an `VERSION_KEYS` und an
`STARTABLE`: „ein Flatpak will `flatpak update`". Sie war ein Missverständnis mit
Folgen, denn `flatpak install` nimmt eine **Bundle-Datei unmittelbar** und
aktualisiert damit eine vorhandene Installation. Ein Repo braucht es dafür nicht,
und der Weg nach draußen stand mit `discover.on_host` seit dem 27.08. schon.

Dazu die Verhältniszahl, die den zweiten Auftrag begründet: Die Installation
besteht zu über 95 Prozent aus Fremdbibliotheken (PySide6 643 MB, scipy 116,
OCP 92, VTK 50, numpy 35 — gegen 5,4 MB eigenen Python-Quelltext). Ein
Wartungsschritt ändert davon fast nichts, das Paket wird trotzdem ganz geladen.

**Was gebaut ist.**

- `updates.install_kind()` unterscheidet sechs Installationsarten statt drei
  Plattformen. Der Unterschied trägt: Flatpak, AppImage und ausgepacktes Archiv
  haben denselben Schlüssel `linux` und drei verschiedene Wege — wer nach der
  Plattform fragt, kann sie nicht trennen.
- **Die Plattform ist ein Parameter**, nach `.claude/rules/kern.md`, und dreimal
  mit `mypy --platform` geprüft. Genau so sind die fünf Stellen entstanden, an
  denen Linux und macOS weniger konnten als Windows: Ein Zweig hinter
  `sys.platform` wird auf der Entwicklungsmaschine nie ausgeführt.
- **Windows läuft still und kommt zurück.** `/SILENT /NORESTART /RESTARTAPP=1`;
  der letzte Schalter ist unserer, ein zweiter `[Run]`-Eintrag im Inno-Skript
  liest ihn. Der vorhandene konnte es nicht — er trägt `skipifsilent`. Nicht
  `/VERYSILENT`: 180 MB packen sich aus, und ohne Balken hielte der Nutzer es
  für einen Absturz.
- **Linux spielt das Flatpak ein und kommt zurück** — `flatpak install` plus
  `flatpak run` als eine Kette auf dem Rechner, weil der Sandkasten gleich
  danach endet. Der Geltungsbereich wird aus `/.flatpak-info` **gelesen**:
  `--user` auf eine systemweite Installation legte eine zweite daneben, und die
  alte startete weiter.
- **macOS bleibt beim `.pkg`** (Entscheidung Robert, 28.08.2026). Der Installer
  zeigt Lizenzvertrag und Ort; `runs_unattended()` trennt die beiden Sätze im
  Dialog, denn „dann startet das Installationsprogramm" über einem stillen Lauf
  ließe den Nutzer ein zweites Mal klicken.
- **„Prüfsumme" ist aus den Kundentexten heraus** (Robert, 28.08.2026): Sie
  interessiert ihn nicht, geprüft *wurde* interessiert ihn. Drei Sätze in sechs
  Sprachen.

Nebenbei gefunden und behoben: `app/ui/panels.py` machte mypy rot, seit
`c4bfd361` — eine `None`-Prüfung innerhalb von `range(item.childCount())`, die
nicht erreichbar ist. Das Tor war damit schon vor dieser Arbeit rot.

Offen:

- [~] **Ab der nächsten Version kommen AppImage und Flatpak auf die
      Download-Seite.** Entscheidung Robert, 28.08.2026: Das AppImage ist der
      direkte Start ohne Terminal, das Flatpak die verwaltete Installation. Das
      Archiv bleibt ein Bauartefakt; sein Installationsskript rechtfertigt keine
      dritte Linux-Wahl. Die Regel steht in `make_download.DELIVERED` und ist
      getestet. Die aktuelle Download-Seite bleibt bis zum Release unverändert.

---

## Ein Changelog in App und Website (28.08.2026)

Entscheidung Robert: Ab der nächsten Version ist der Verlauf nicht nur in der
Anwendung nachlesbar, sondern genauso sauber und kundenorientiert auf der
Website. In beiden Oberflächen soll ein Auswahlfeld durch alle Fassungen
führen; ein zusätzlicher Pflegeschritt soll daraus nicht entstehen.

- [x] **Eine Quelle, zwei automatisch erzeugte Oberflächen.**
      `changelog/<sprache>.md` bleibt die einzige gepflegte Quelle. Das
      Neuerungen-Fenster öffnet auf der laufenden Version und zeigt über sein
      Auswahlfeld jede mitgelieferte Fassung einzeln. `make_changelog.py`
      erzeugt daraus die sechs responsiven Webfassungen; `make_download.py`
      ruft es bei jedem Release automatisch auf. Ein Gleichheitstest hält die
      erzeugten Seiten gegen die Quelle, und Sitemap, Sprachwechsel sowie
      Inhaltsstempel sind angeschlossen. Desktop- und Handyansicht sind im
      lokalen Browser geprüft; der Auswahlwechsel zeigt genau einen Abschnitt
      und trägt die Fassung in der Adresse.

---

## Der Verkaufsstart und die vorerst entfallene Testphase (28.08.2026)

Robert hat den Termin festgelegt: Demo bis einschließlich 30.10.2026, am
31.10. kein Demostart mehr und ab 01.11. Verkauf. Zunächst war dafür ein
vierzehntägiger Testlauf vorgesehen. Die Prüfung unten fand den Bruch, den ein
solcher Wechsel für bisherige Demo-Nutzer verursacht hätte.

**Was schon steht, und es ist viel.** `TRIAL_DAYS = 14` liegt fest, der echte
öffentliche Lizenzschlüssel ist eingetragen (kein Platzhalter),
`tools/make_licence_keys.py` stellt Kundenschlüssel aus — personalisiert oder
als Vorrat für einen Zahlungsanbieter. Der Umschalter von Demo auf
Verkaufsversion ist **eine Zeile**: `DEMO_UNTIL = date(2026, 10, 30)` → `None`
in `app/core/activation/store.py`, und `days_left()` nennt sich selbst „die eine
Stelle, an der sich Demo und Verkaufsversion unterscheiden".

**Was daran bricht.** Beide Zweige schreiben denselben Testlaufmarker, mit
`first_run` = Tag des ersten **Demo**-Starts. Nach dem Umschalten rechnet
`trial_days_left()` also `used = (heute − erster Demo-Start)`. Gemessen in einem
isolierten Profil:

| Marker | am 01.11.2026 | am 20.11.2026 |
|---|---|---|
| erster Start 20.08. (Demo-Nutzer) | **0 von 14 Tagen** | 0 |
| kein Marker (Neukunde) | 14 | 14 |

Die Untergrenze, die es dort schon gibt, greift nicht: Sie hebt `first_run` nur
an, wenn er **vor** `DEMO_FROM` liegt — und `DEMO_FROM` ist der 20.08.2026,
also genau der Tag, an dem die Demo erschien. Ein Marker von diesem Tag bleibt
stehen; am 01.11. sind das 73 Tage `used`. Von formwerk-af unabhängig am Code
nachgeprüft.

Der Kunde erlebt das so: kostenlos genutzt, Update gemacht, alles zu, kaufen —
und die vierzehn Tage, die die Website nennt, bekommt er nie zu sehen.

**Spätere Entscheidung Robert, 28.08.2026 — ersetzt die vorige:** Die
vierzehntägige Testphase ist zum Verkaufsstart vorerst hinfällig. Sie soll im
Code sauber, aktuell und getestet bleiben, damit ein späterer Release sie ohne
Umweg ausdrücklich aktivieren kann. Für die ausgelieferte Verkaufsversion gilt
deshalb `TRIAL_FROM = None`; `TRIAL_DAYS = 14` und der gehärtete Markerpfad
bleiben als deaktivierte Fähigkeit erhalten.

Offen:

- [x] **`SALE_FROM` wird zum Verkaufsstart nicht gebraucht.** Es müsste nur
      einen angebotenen Testlauf von einem alten Demo-Marker abgrenzen. Weil
      `TRIAL_FROM = None` keine Testphase anbietet, wertet `days_left()` den
      vorhandenen Marker nicht als Freischaltung und erzeugt auch keinen neuen.
      Ein eigener Gegenbeweis legt einen alten Marker in eine Verkaufsversion
      und prüft: Sie ist gesperrt, aber ausdrücklich **nicht** als abgelaufener
      Test markiert; alles Lesende bleibt offen. `sale_without_trial` trennt
      diesen Zustand von `expired`, damit Chat, Slicer, Menüs, Über-Dialog und
      Handbuch keinen nie angebotenen Test behaupten. Falls die Testphase
      später aktiviert wird, bekommt dieser Release
      einen bewusst gewählten `TRIAL_FROM`-Stichtag und die hier bereits
      durchgerechneten Migrationsprüfungen.
- [x] **Freischaltung für Kunden ohne Lizenz- oder CAD-Vorwissen durchgezogen.**
      Der Dialog führt in zwei beschrifteten Schritten vom Kaufcode zur einmaligen
      Geräteaktivierung; ein gültiger, aber noch nicht aktivierter Code heißt in
      keinem Status mehr „lizenziert“. Der Offline-Ausweg besteht aus drei
      nummerierten Schritten, übernimmt die Sprache der Anwendung, bleibt ohne
      Konto nutzbar und nennt bei Datei-, Netz- und Serverfehlern den nächsten
      Weg. Website, Handbuch und alle sechs Oberflächensprachen sagen gemeinsam:
      Zum Verkaufsstart gibt es keine Testphase, der gepflegte 14-Tage-Pfad ist
      lediglich deaktiviert.
      Die Nachdurchsicht vom 28.08.2026 hat außerdem die fünf Anschlüsse
      geschlossen: Der macOS-Vertrauensspeicher wird wirklich beim Start
      gesetzt; eine verlorene Abmeldeantwort bleibt als sicher wiederholbarer
      Auftrag bestehen; die Serversicherung vereinigt Hauptdatei und WAL;
      alte Tageszähler werden beim nächsten gültigen Zugriff bereinigt und in
      der Datenschutzerklärung genannt; der Videotext folgt direkt dem
      Demo-/Teststand des jeweiligen Baus.
- [x] **Private Support-Verwaltung für den Verkaufsstart gebaut.**
      `tools/licence_admin.py` ist eine lokale, nicht ausgelieferte Oberfläche:
      Sie ordnet einen anonymen Vorratsschlüssel lokal der Transaktionskennung
      aus dem MoR-Dashboard zu und findet eine Lizenz im externen
      Schlüsselarchiv nach vollständigem Schlüssel, Digest, Transaktion,
      Bestell-/POOL-Kennung oder Käuferkennung, zeigt
      Aktivierungen, Tageszähler und Änderungsprotokoll und kann neue
      Aktivierungen sperren/freigeben, den Geräteplatz für einen Wechsel
      freigeben und ein geklärtes Versuchslimit zurücksetzen.
      `api/operator.php` nimmt ausschließlich den extern erzeugten
      256-Bit-Betreiberzugang an; zum Server geht nur der Digest, nie das Archiv
      oder die Käuferkennung. Jede Änderung trägt einen festen Anlass ohne
      Freitext. Die Oberfläche sagt die Offline-Grenze sichtbar: Eine schon
      ausgestellte Freischaltung wird nicht fernabgeschaltet. Der
      Schlüsselgenerator verlangt jetzt das private JSONL-Archiv und schreibt
      es atomar vor der Ausgabe, damit ein Supportfall identifizierbar bleibt.
      Die Abschlussdurchsicht hat den Altbestand eingeschlossen: Das Deployment
      akzeptiert die bestehende Drei-Tabellen-Datenbank bis zur idempotenten
      Migration, Generator und Oberfläche teilen eine Betriebssystem-Sperre und
      verifizieren vor jeder Änderung das vollständige Archiv. MoR-Transaktionen
      sind eindeutig, ältere Hauptversionen bleiben über den Schlüssel suchbar.
      Die Oberfläche führt ohne CAD-Begriffe in drei nummerierten Schritten und
      kodiert jeden Zustand zusätzlich zu Farbe als Symbol und Klartext.
- [x] **Der Ollama-Pull im Chat-Dialog endete im Test auf „nicht geantwortet".**
      `tests/test_chat_ui.py::test_the_pull_shows_a_share_and_a_way_out` erwartet
      „liegt jetzt hier" in `KeyDialog.probe_result` und las „Ollama hat nicht
      geantwortet — läuft es noch?". Ursache war der Prüfstand: Seit lokale
      Dienste Firmenproxies bewusst umgehen, öffnet `pull_model()` über
      `opener_for(...).open`; der Test ersetzte weiter das nicht mehr benutzte
      `urllib.request.urlopen` und sprach deshalb mit dem echten lokalen Port.
      Der Ersatz folgt jetzt dem wirklichen Vertrag; Knopf, Arbeiter,
      Fortschritt und Thread-Signal sind gemeinsam geprüft.
- [ ] **`rtree` liegt auf Entwicklungsmaschinen als Überrest und macht vier
      Tests rot.** Es ist am 24.08.2026 aus `pyproject.toml` entfernt und durch
      `app/core/geom/enclosure.py` ersetzt worden, steht seither auf der
      Sperrliste (§36) — installiert bleibt es trotzdem, weil eine
      Deinstallation kein Teil eines `git pull` ist. Rot werden dadurch
      `test_licences.py` (3) und `test_acceptance_p0.py` (1). Behebung ist ein
      Befehl je Maschine: `python -m pip uninstall -y rtree`; danach 27 grün.
      Auf **dieser** Maschine am 28.08. erledigt. Der Punkt bleibt offen, bis er
      auf allen drei gelaufen ist — er sieht wie ein Codefehler aus und ist
      keiner, und das kostet beim nächsten Mal wieder eine halbe Stunde Suche.

## ComfyUI aus Solidon starten (28.08.2026)

Robert zeigte die Zeile aus *Hilfe → Zusätzliche Programme*: ComfyUI Desktop
war installiert, Solidon meldete „nicht gefunden“, und *Ort angeben …* fragte
ausschließlich nach einer HTTP-Adresse. Damit führte der einzige sichtbare
Knopf gerade nicht zu dem Programm, das ein Kunde von comfy.org bekommt.

- [x] **Desktop und Webdienst sind jetzt zwei Seiten derselben Zeile.** Erkannt
      werden `Comfy Desktop`, die älteren Programmnamen und die offizielle
      `comfy`-Kommandozeile. Ein gefundenes, noch nicht antwortendes ComfyUI
      bekommt *Lokal starten*; Desktop wird geöffnet, die CLI dokumentiert mit
      `launch --background` gerufen. Die Portprüfung läuft im Arbeiter.
- [x] **Pfad und Adresse überschreiben einander nicht mehr.** Der gemeinsame
      Speicherplatz machte aus `C:\…\Comfy Desktop.exe` zugleich die angebliche
      Webadresse des Backends. Beide Angaben haben nun getrennte Schlüssel mit
      Rückfall auf die alte Datei. *Ort angeben …* bietet entsprechend *Lokale
      App auswählen …* und *Web-/Netzadresse verwenden …* an. Der lokale Start
      prüft und aktiviert immer Port 8188; eine gespeicherte Netzadresse bleibt
      dabei erhalten und kann später wieder ausgewählt werden.
- [x] **Am Rechner des Fundes nachgemessen.** Die Erkennung liefert
      `C:\Users\rober\AppData\Local\Programs\Comfy Desktop\Comfy Desktop.exe`,
      der Startbefehl genau diese Datei und die Backend-Adresse weiterhin
      `http://127.0.0.1:8188`.

---

## Teilen und Zeichnen ohne CAD-Vorwissen (29.08.2026)

Robert fand an den zwei Fusion-nahen Hauptwegen dieselbe Lücke: Beim Teilen
war nicht erkennbar, welche Ebene wirklich durch den Körper läuft, und die
Passstifte verschwanden anschließend zwischen deckungsgleichen Hälften. Beim
freien Zeichnen gab es Hochziehen und Abtragen zwar als Ziehgriff in der
Querschau, aber nicht als sichtbare nächste Handlung.

- [x] **Die Teilung zeigt und behält genau die gezeichnete Ebene.** Der zweite
      Punkt friert die Ebene samt Blickrichtung ein; ein späteres Drehen der
      Kamera ändert den Schnitt nicht mehr. Im Modell steht eine
      durchscheinende, umrandete Fläche mit sichtbarem Überstand statt nur
      einer Linie. Beide Punkte müssen auf demselben Teil liegen. Nach der
      Auswertung öffnet Solidon die Hälften automatisch in der
      Explosionsansicht und nennt ausdrücklich: Stifte an Teil A, Löcher an
      Teil B. Dasselbe gilt für die registrierte Operation *Teilen* und die
      automatische Bett-Teilung.
- [x] **Hochziehen und Abtragen stehen direkt an einer geschlossenen freien
      Skizze.** Zwei beschriftete Knöpfe mit unterschiedlichen Symbolen führen
      ohne den Fachbegriff „Extrusion“ in die Höhen- beziehungsweise
      Tiefenangabe. Ein offener Umriss nennt seine Bedingung am gesperrten
      Knopf; Abtragen verlangt zusätzlich genau einen ausgewählten exakten
      Körper und erklärt, wie ein Dreiecksnetz ersetzt werden kann. Der
      sichtbare Ziehgriff in Vorder- oder Seitenansicht bleibt als schneller
      Direktweg erhalten.
- [x] **Die Viewport-Darstellung des Skizzenmodus ist vollständig nachgezogen
      (29.08.2026).** Das Modell tritt auf 16 Prozent Deckkraft ohne Schatten
      und Auswahlfärbung zurück. Das Raster besitzt feine Linien,
      Fünfermarken, farbige und beschriftete Nullachsen; Skizzenkanten stehen
      in Hinweisblau, Auswahl und Live-Vorschau in Bernstein. Unfertige
      Linien, Kreise, Bögen, Splines und Rechtecke erscheinen zwischen den
      Klicks im echten Viewport, Maße als lesbare Karten. Nach geschlossenem
      Umriss führt eine Karte zur Vorder-/Seitenansicht; dort stehen
      *Hochziehen* und *Abtragen* direkt am Pfeil/Kreuz. Die Kamera hält Profil
      und Griff automatisch oberhalb der schwebenden Leiste. Deren leere
      Canvas-Zeile und der umbrechende Schichthinweis sind entfernt; gemessen
      schrumpfte sie von 292 auf 142 Bildpunkte. Drei echte Aufnahmen —
      Draufsicht, Querschau und laufendes Rechteck — wurden nach jedem
      Umbau angesehen, nicht nur über Actors geprüft.

---

## Langer Verlauf und modularer Besteckkorb (29.08.2026)

Der modulare Kundenstand machte zwei Fehler gemeinsam sichtbar: Ein warmer
Verlauf traf zwar den Geometriecache, untersuchte aber trotzdem jeden
Zwischenkörper erneut; beim wiederholten Teilen verschwanden frühere
Passungen, weil jede neue Naht wieder `pin_1` und `bore_1` vergab.

- [x] **Merkmalcache trägt lange reale Verläufe.** Seine frühere Grenze von 32
      war nach der Zahl fertiger Objekte begründet, tatsächlich sieht die
      Erkennung aber das Netz nach jeder Operation. Der gemessene
      Ausgangsstand hatte bei 163 Operationen 132 verschiedene Zwischenkörper;
      der fertige Stand umfasst 174 Operationen. Die weiterhin feste Grenze
      256 hält den Ausgangsverlauf vollständig: unverändert erneut 0,215 s,
      nach einer Verschiebung 0,304 s statt vorher rund 20,5 s. Ein
      Korpustest mit genau 132 Zwischenständen schützt gegen das LRU-Flattern.
- [x] **Erneutes Teilen erhält bestehende Verbindungen.** Neue Verbinder
      beginnen hinter der höchsten vorhandenen Nummer. Frühere erzeugte
      Merkmale reisen anhand ihres Mittelpunktes auf das geometrisch richtige
      Kindstück, und ihre Passungen werden in derselben Transaktion dorthin
      umgehängt. Liegt ein Merkmal genau im Schnitt oder hat keinen
      verlässlichen Mittelpunkt, bleibt die bisherige vorsichtige Antwort:
      entfallen und melden, nicht raten.
- [x] **Kundenprojekt vollständig über die Oberfläche neu aufgebaut.** Der
      sichtbare Teilungsweg erzeugt sechs verständlich benannte Module, vier
      Schwalbenschwänze je Naht, 20 geprüfte Passungen und drei tragende
      Wandbahnen. Alle sechs Module sind wasserdicht und je eine Komponente;
      zwei Platten halten 6,0 mm Mindestabstand. Projekt und 3MF liegen unter
      `3D Drucker/13_Besteckkorb_Abtropfkorb/Modular/`.
- [x] **Eigenständig geprüfte Viewports sterben erst nach der
      Zusammenfassung.** Der Suite-Pin hielt bisher nur `MainWindow`; die
      Ansichtsdatei baut den VTK-Viewport dagegen bewusst ohne Hauptfenster.
      Sie endete deshalb nach 100 Prozent dreimal nacheinander mit
      `0xC0000374` statt einer Zusammenfassung. Derselbe Lebenszeitvertrag
      gilt jetzt für beide Typen; die drei Tests, die Freigabe absichtlich
      messen, nehmen sich über `unpinned_windows` aus. Gegenprobe: dreimal
      94 Tests, dreimal Exit 0; die drei betroffenen Fensterdateien danach
      einzeln 81 Tests, Exit 0.

---

## Sechs Leistungsmarken rissen einen Zähler, und der Code war unschuldig (30.08.2026)

Sechs Marken standen rot, und zwei Erklärungen sind nacheinander an der
Messung gefallen: Es waren keine Budgetverletzungen (fünf der sechs reißen den
Regressionszähler `strikes` bei teils dreißigfach unterschrittenem Budget —
`sculpt_replay_1000` misst 69 ms gegen 2000 erlaubte), und es war nicht der
`deferred`-Import (die frühere Registerzeile behauptete das; die Messreihe
gegen `1f3426eb`, den Stand **vor** dem Umbau, widerlegt es).

Die Messreihe, zwei Worktrees mit geleerter `.performance.json`, freie
Maschine, Kontext `alone`:

| Marke | vor `deferred` | HEAD | Baseline-Bestwert | Budget |
|---|---|---|---|---|
| sculpt_replay_1000 | 70 ms | 72 ms | 46 ms | 2000 ms |
| sculpt_apply_1000 | 97 ms | 100 ms | 64 ms | 2000 ms |
| subdivide_surface | 1893 ms | 1863 ms | 1173 ms | 3000 ms |
| remesh_uniform | 1565 ms | 1538 ms | 947 ms | 3000 ms |
| boolean_medium | 854 ms | 834 ms | 451 ms | 20000 ms |
| orient_200 | 18682 ms | 18774 ms | — | 20000 ms |

Alt und neu liegen unter drei Prozent auseinander, vier von sechs sind auf
HEAD schneller. Die Bestwerte dagegen sind auf **keinem** der beiden Stände
reproduzierbar — Faktor 1,5 bis 1,9 darunter, gleichmäßig über alle Marken.
Keine Code-Änderung macht fünf verschiedene Rechnungen gleichmäßig um zwei
Drittel langsamer; eine günstige Maschinenphase erklärt genau das. Beide
Stände sind in sich stabil (Zweitläufe je unter drei Prozent Abweichung).

**Der eigentliche Fehler ist die Mechanik, nicht die Zahlen:** Ein Bestwert
als Minimum über alle Läufe kann nur sinken, nie steigen — ein einziger
günstiger Lauf legt ihn für immer fest, und jeder normale danach gilt als
Regression. Der `alone`-Kontext ist der einzige mit Strikes; neun weitere
Kontexte stehen bei null, ihre Bestwerte liegen 30 bis 50 Prozent höher.
Damit löst sich auch die Registerzeile vom 26.08. („`orient_200` streut über
die Regressionsschwelle") hier mit auf: 18,7 s auf beiden Ständen dicht unter
dem 20-s-Budget ist eine zu knapp gesetzte Bestmarke, kein Regressionsfall.

- [x] **Erledigt mit `b26405d0` (30.08.2026):** Median über die letzten
      `WINDOW = 5` Läufe je Kontext statt ewigem Minimum, `MIN_RUNS = 3`
      gegen die Migrations-Delle (der alte Bestwert zieht als einzelner
      Lauf ein und ist selbst der Ausreißer), alle drei Altformate bleiben
      lesbar, der Zähler beginnt beim Formatwechsel neu. Die
      Messverfahrens-Entscheidung steht im selben Commit in
      `.claude/rules/tests.md`; die Mechanik selbst prüft
      `tests/test_performance_marks.py` im Tor (sechs Tests, gestellte Uhr,
      auch die Gegenrichtung: eine echte Verlangsamung um mehr als ein
      Viertel reißt weiterhin). Vier Läufe in Folge grün aus der migrierten
      echten Baseline, nachverifiziert im Probe-Worktree gegen eine Kopie
      derselben.

---

## Die Parameterkarte war im Betrieb breiter als ihre Zone (30.08.2026)

Der Reihenfolge-Befund hat sich beim Messen umgedreht: Der rot geglaubte Test
sagte die Wahrheit. Mit dem Stylesheet aus `apply_theme` — das jedes Fenster
über die QApplication legt, die Lage „ohne" gibt es beim Kunden nie — misst
die Parameterkarte 270 Bildpunkte in einer Zone von 260; ohne Stylesheet 258,
und nur so, allein gefahren, war der Test grün. Zwei falsche Erklärungen
fielen unterwegs: die hängengebliebene Sprache (270 entsprach zufällig exakt
dem französischen Wert — eine Sonde über 407 Tests fand null Sprachwechsel)
und das bloße Aufräumproblem (eine Rücksetz-Fixture hätte den Kundenfehler
dauerhaft zugedeckt). Die Regel dazu steht in `.claude/rules/tests.md` unter
„Isolation heißt Betriebslage, nicht Nullzustand".

Gebaut und einzeln abgenommen, im Baum wartend auf ee's Bündel-Commit:
`LEFT_WIDTH` 260 → 272 (gemessen, mit 1280er-Gegenprobe: dem Modell bleiben
660 Bildpunkte), der Test stellt die Betriebslage selbst her, die
`set_language`-Rücksetzung nach dem Muster der Anzeigeeinheit, und der
`['Home']`-Fall des Kürzeltests (Qt übersetzt Tastennamen über seine eigene
Locale — auf Deutsch heißt die Taste „Pos1"; verglichen wird jetzt über
dieselbe Funktion, die anzeigt). Dazu die leash-Eingänge, die Nicht-Arbeiter
abweisen — der Fremdkörper kam aus einem Test, der Suite-Pin machte den
jahrelang latenten Fall nur sichtbar.

- [x] **Geschlossen mit `acf47923`** — das Bündel ist committet, und die
      Abnahme lief vorher im Probe-Worktree: `test_ui` plus
      `test_interface_limits` mit 407 grünen Tests, beide Reihenfolge-Tests
      darunter, alle sechs abgeleiteten Testfamilien einzeln je Prozess
      Exit 0.

---

## Wortgleiche Waisen-Hinweise fluten den Prüfbericht (30.08.2026)

Nach einem Weg-3-Erzeugungslauf stehen 123 Befunde im Prüfbericht, und 118
davon sind wortgleich: „Ein Merkmal hat keinen Nachfolger mehr."
(`perceive.orphaned`, je Merkmal eine eigene Zeile). Die fünf Zeilen, die
etwas sagen — `transform.fitted`, drei `repair.*`, `arrange.below_bed` —
gehen darin unter. Der `info`-Grad ist bewusst gewählt und in `evaluate.py`
begründet; bedacht ist der **Grad**, nicht die **Menge**.

Warum die Menge zählt, obwohl jede Zeile für sich stimmt: `arrange.below_bed`
nach einem Erzeugungslauf ist **richtig** (§17.1, geprüft am 30.08.2026 — der
erzeugte Körper liegt wirklich unter dem Bett, bis die Übernahme ihn hebt).
Gerade der korrekte Hinweis, den der Kunde lesen sollte, ist neben 118
gleichlautenden nicht mehr zu finden.

- [x] **Entschieden und gebaut** (72, `f3f3f993`): Zusammenfassen statt
      Deckel, und in der Anzeige statt im Kern — Agent, CLI und
      Steckbrief lesen weiter jeden Befund einzeln. `_bundled()` in
      `panels.py` fasst wortgleiche Befunde (Kennung, Grad, Wortlaut)
      ab vier zu einer Zeile: „118 × Ein Merkmal hat keinen Nachfolger
      mehr", die Zahl im Zeilentext (Regel 18), die Betroffenen im
      Tooltip (erste fünfzehn, Rest beziffert), gleicher Wortlaut mit
      anderem Grad nie zusammen. Die Kopfzeile zählt die Befunde statt
      der Zeilen, über eine eigene Item-Rolle — `values["count"]`
      führen auch Kernbefunde, und eine Zählung, die ihn läse, zählte
      deren Zahl statt ihrer Zeile. Zwei Tests am gebauten Bericht
      (6 Zeilen statt 123, Schwellenrand 3/4); Gegenprobe: ohne
      Bündelung fallen beide.

---

## Das Budget der Orientierungssuche lässt keinen Puffer (30.08.2026)

`orient_200` misst 18 682 ms auf dem Stand vor dem `deferred`-Umbau und
18 774 ms auf HEAD — stabil, keine Regression, aber nur gut sechs Prozent
unter dem 20-s-Budget aus §31. Ein schlechter Maschinentag kippt die Marke
über die Grenze, ohne dass eine Zeile langsamer wurde.

- [x] **Erledigt durch Nachmessung** (15/53, 30.08.2026, drei Läufe
      unter dem Schloss): Median 12,05 s gegen 20 s Budget — die 18,7 s
      stammten vom Stand **vor** der Einmal-je-Lage-Optimierung; seit
      ihr hat die Marke 40 Prozent Luft, und weder Budget noch Suche
      brauchen eine Änderung. Roberts Entscheidung erübrigt sich.
      Ehrlichkeits-Fußnote: In historischen Sammellauf-Fenstern stehen
      auch 15–26 s — das ist das bekannte Fremdlast-Thema; die
      §31-Messweise ist solo, und solo hält sie.

---

## Eine Kunden-3MF hängt vier Minuten im Hash (30.08.2026)

Der UI-Audit der Nacht fuhr zwölf Projekte und 58 Modelle ohne eine einzige
Ausnahme — nur `59 Cat_Toys_V2.3mf` brach nach vier Minuten mit Timeout ab.
Der Stack steht in `threemf.read_objects` → `trimesh.copy` →
`caching.hash_fallback`, während der Hauptthread gleichzeitig einen Autosave
schreibt. Das ist ein Leistungsbefund, kein Absturz.

- [x] **Diagnose am echten Fall** (72, 30.08.2026 — 25 Teile, 604 146
      Dreiecke, 10,2 MB), voller Kundenweg am frischen Prozess: 14–15 s,
      kein Hänger — read_objects 2,8 s, Autosave 0,2 s bei 9,9 MB; der
      Audit-Stack war ein einzelnes Timeout-Sample, die wahrscheinlichste
      Erklärung der vier Minuten ist der Prozesszustand des Nacht-Audits
      nach 57 Modellen (native-Familie). Gefunden hat die Messung
      stattdessen: **xxhash stand nie in den Abhängigkeiten**, trimesh
      fiel still auf blake2b zurück — 298 992 Aufrufe und 3,4 s je
      Auswertung dieser Baugruppe, und weil PyInstaller nur bündelt, was
      die Bau-Umgebung hat, fuhr jedes ausgelieferte Paket den langsamen
      Weg. Behoben mit `dedd2b8d`: xxhash (BSD-2-Clause) nach der
      Abhängigkeits-Checkliste, in der Spec ausdrücklich als
      Paketvertrag; Gegenmessung 14,0 statt 15,2 s. Die Kundendatei
      bleibt draußen (fremde Lizenz); die Leistungsmarke ist gebaut
      (`905eb4ff`): `ingest_assembly`, 25 Teile / gut 500 000 Dreiecke
      zur Laufzeit erzeugt, Aufbau vor der Uhr, Budget 30 s absolut bei
      gemessenen 1,8 s — samt Gegenprobe, dass der threemf-Kopfimport
      trimesh nicht vorzeitig lädt.
- [ ] **Prüfpunkt nächster CI-Bau**: Liegt xxhash im gebauten Paket?
      Erst dann ist die Kundenwirkung belegt, nicht nur die der
      Entwicklungsumgebung.

---

## Solidons Elegoo-Lauf scheitert, die CLI selbst nicht (30.08.2026)

Der Auftrag „mit allen Slicern ohne Probleme" ist bis auf diesen Fall
erledigt: Die Auswahl bei mehreren Slicern ist gebaut (`67a54a8c` — einer je
Installationsordner, die Wahl bleibt gemerkt, der Wechsel leert die Profile
des alten Slicers), PrusaSlicer und CuraEngine laufen Ende zu Ende mit
gemessenen G-Code-Kennzahlen.

Bei ElegooSlicer widersprachen sich zwei Messungen auf derselben Maschine,
und die zweite hat die erste widerlegt: Solidons Lauf brach mit
`Slic3r::CLI::run found error`, Exit −17 — aber die CLI selbst slicet
einwandfrei (55, zweimal: Elegoos eigene Systemprofile ECC2/0.4/0.20/PLA,
Exit 0, 1577 mm Filament, 18 min 26 s, stimmig neben der
PrusaSlicer-Referenz, Version 1.5.3.4). Die frühere Fassung „scheitert auch
ohne Solidon" beruhte auf einer erinnerten Kommandozeile, die niemand
aufgehoben hatte — eine erinnerte Zeile ist kein Beleg.

Solidons Aufruf (`handover.py:1524–1545`) ist strukturell identisch mit der
funktionierenden Handzeile bis auf zwei messbare Unterschiede: `--arrange 0`
(ob 1.5.3.4 den Schalter kennt, steht nirgends — ein unbekannter Schalter
endet bei dieser Familie erfahrungsgemäß im stillen Abbruch; Hauptverdacht)
und das von `write_config` selbst geschriebene Maschinenprofil statt Elegoos
Original. Ein `layer_gcode` mit `G92 E0` wird nicht eingebaut — Robert: „den
gcode wollen wir nicht verändern, nur die vorgaben bei den slicern" (§22).

- [x] Geschlossen am 30.08.2026, in zwei Messungen: fb's Trennläufe (auf der
      Handzeile mit Elegoos Systemprofilen) wiesen den Schalterwert 0 als
      alleinige Ursache aus — `--arrange 1` läuft, die abgelehnte
      **Wertbelegung** ist gerade das „nicht anordnen". Der Fix ist die
      Rückfallstufe in `153c942d`: einmal ohne den Schalter, die verworfene
      Anordnung als Befund (`slicer.arranged_itself`), das Programm je
      Sitzung gemerkt. Und der echte Ende-zu-Ende-Weg ist belegt (55):
      Solidons voller Aufruf mit selbst geschriebenem Maschinenprofil gegen
      ElegooSlicer 1.5.3.4 — Abbruch an `--arrange 0` in Sekundenbruchteilen,
      der Rückfall liefert `plate_1.gcode` mit 100 Schichten und 1568,6 mm
      Filament (stimmig zur Referenz), der Befund kommt in beiden Läufen,
      die zweite Platte läuft gemerkt in einem Zug (3,2 s statt 3,9 s).
      Damit ist auch das eigene Maschinenprofil am echten Weg bestätigt,
      nicht nur auf der Handzeile entlastet.

---

## Der Chat-Kontext ist nach einem Objekt zu drei Vierteln voll (30.08.2026)

5ds Ollama-Messung an Weg 3 (30.08.2026): Nach einem einzigen erzeugten
Objekt meldet das Modell rund 76 Prozent seines Kontextfensters als belegt.
Die Notiz im Code rechnet mit etwa 13 500 Token Grundlast — die Beobachtung
sagt, dass Steckbrief und Werkzeugantworten schneller wachsen, als diese
Zahl vermuten lässt. Eine einzelne Beobachtung, keine Messreihe; der
ehrliche Messweg ist `prompt_eval_count` aus der Ollama-Antwort, nicht eine
eigene Token-Schätzung (dieselbe Falle wie jede Zählung, die der Prüfling
selbst liefert).

- [x] **Messreihe gefahren** (72, 30.08.2026 — qwen3:14b, num_ctx
      32 768, echter AgentSession-Weg, `prompt_eval_count` vom Backend):
      Grundlast **24 120 Token = 74 % VOR dem ersten Objekt**; Zug 1:
      24 475 (75 %), Zug 5 bei 7 Ops: 26 870 (82 %) — Wachstum ~600
      Token je Zug. „Nach drei bis vier Objekten Schluss" ist damit
      widerlegt: Das Fenster trägt ~14–15 Züge, und die Stellschraube
      ist die **Grundlast** (Werkzeugschemata, Systemprompt,
      Regelsammlung), nicht der Steckbrief.
- [ ] **Die Grundlast senken** — kompakte Werkzeugschemata zuerst
      (Empfehlung der Freigabe, 30.08.2026: Grundlast vor
      Kürzungsstrategie, denn sie wirkt auf jeden Zug ab dem ersten);
      eine Kürzungsstrategie ab Zug ~12 bleibt die Rückfallebene.
      Messlatte: dieselbe Reihe, gleiche Züge, Grundlast deutlich
      unter 24 120.

---

## Die zweite Übergabeart ist gebaut und hängt an nichts (30.08.2026)

`open_in_slicer` (§29) öffnet die geschriebene Druckdatei im Fenster des
Slicers — für den Fall, dass die Kommandozeile eines Slicers nicht kann, was
sein Fenster kann, und für den Kunden, der im Slicer selbst weiterarbeiten
will. Lizenzgrenze, Fehlerwege mit Handlungsvorschlägen und Tests stehen
(Commit A von 55, 30.08.2026); die Fenster-Suche kennt die getrennten
Programme der Prusa- und Cura-Familie. Was fehlt, ist der Aufrufer: kein
Treffer in `app/` außerhalb von `handover.py`. Eine gebaute Funktion ohne
Anschluss ist ein Versprechen, das das Produkt noch nicht gibt — mit Ansage
hier festgehalten statt still (eine Kette endet am letzten Glied).

- [x] Erledigt mit `94f976a2` (30.08.2026): „Im Slicer öffnen …" steht als
      zweiter Knopf neben „Slicen" — zwei Handlungen, keine Betriebsart. Die
      benutzte Art reist als `handover`-Feld in den Druckeinstellungen mit
      (tolerant in beide Richtungen, Fremdwert fällt auf „slice") und macht
      beim nächsten Aufbau ihren Knopf zum Hauptknopf; gemerkt wird bei
      Nutzung, nie bei Ansicht. Ein Slicer ohne Fenster sperrt den Knopf
      mit Grund in beiden Kodierungen. Handprobe an allen drei Familien:
      je Datei ein eigenes Fenster, keine stille Ersetzung; ElegooSlicers
      eigene „Load Whole File"-Nachfrage bleibt sein Dialog, die Quittung
      sagt ehrlich „das Fenster gehört jetzt Ihnen".

---

## Gespeicherte Slicer-Profile überleben den Slicer-Wechsel (30.08.2026)

`_remember_slicer_choice` kehrt früh zurück, wenn alle drei Auswahlfelder
leer sind — damit eine leere Auswahl die gute nicht überschreibt. Nach
einem Wechsel auf PrusaSlicer oder CuraEngine sind sie aber **immer**
leer, denn die brauchen keine Profile: Der Orca-Bestand blieb gespeichert
und wurde beim nächsten Start wieder aufgelegt (fb, gemessen über den
Klickweg). Das Vermerkfeld `slicer_profile_slicer` in `app/ui/settings.py`
liegt seit `83a05d38`; was fehlt, ist die andere Hälfte — samt dem Fall
„Vermerk leer", der jede Installation von vor dem Feld beschreibt: Ohne
diese Ausnahme verlöre jeder Bestandskunde seine Profilwahl beim ersten
Update.

- [x] Erledigt mit `f85c8575` (30.08.2026): `_remember_slicer_choice`
      schreibt den Slicer-Pfad zum Bestand, `remembered_setup` verwirft
      Fremdes; leerer Vermerk heißt „von früher", dann wird nicht
      verglichen — die Bestandskunden-Ausnahme. Der Commit-Text nennt den
      realen Schaden ehrlich (Export-Setup und Dialog-Vorbelegung) statt
      des gemessen widerlegten „der Slicer lehnt ab" — die Prusa-Konsole
      liest das fremde Maschinenprofil gar nicht.

---

## Ein Rat bleibt stehen, den dieselbe Kette schon befolgt hat (30.08.2026)

Nach einem Weg-3-Erzeugungslauf meldet der Prüfbericht
`ingest.very_large` mit dem Rat „‚Dreiecke verringern' hilft" — und
`decimate_mesh` steht als vierter Schritt **desselben Stapels**, das
Objekt hat längst 150 000 Dreiecke (5d, gemessen am Textweg-Lauf). Der
Befund entsteht beim Laden, wo er mit 614 820 Dreiecken wahr ist;
erledigt hat ihn Schritt vier derselben Kette, und der Bericht sammelt
über alle Schritte. Der Fall ist Weg-3-eigen: Beim Import dezimiert
nichts automatisch, nur die Erzeugungskette räumt hinter sich auf. Der
Kunde liest einen Handlungsvorschlag für etwas, das die Anwendung im
selben Zug getan hat — muss er raten, ob er noch klicken soll, ist es
falsch.

- [x] **Erledigt** (15/53, `198e0009`, 30.08.2026): `ingest.very_large`
      steht in `SETTLED_BY` und wird vom `mesh.deviation`-Befund
      derselben Kette gestrichen — der Weg-3-Kunde liest keinen Rat mehr
      für etwas, das Schritt vier längst getan hat. Bleibt die
      Dezimierung über der Erkennungsgrenze, trägt der frische
      `perceive.too_large` die Auskunft weiter; der Dauer-Rat für die
      Kartenzone entfällt bewusst (Karten melden beim Klick selbst).
      Rot-Probe dokumentiert: beide Tests vor dem Eintrag rot.

---

## Die read_dense-Marke misst je nach Sammelumfang zwei verschiedene Dinge (30.08.2026)

`_invocation_key` in `tests/test_performance.py` zählt die **ausgewählten**
Dateien — und nach `-m performance` über die ganze Suite bleibt nur
`test_performance.py` übrig, derselbe Schlüssel wie beim Lauf der einen
Datei. Für genau **eine** Marke sind die zwei Lagen verschieden:
`read_dense` ist der erste Test der Datei und der einzige, der trimesh
braucht. Beim Suitenlauf zieht das Sammeln den Import vorher; allein trägt
ihn die Messung. fb's Messreihe (30.08.2026): 1072 ms allein gegen 427–443
im Volllauf, beide unter `alone` — und die anderen fünf Marken sind
nachgemessen **nicht** betroffen (sie laufen hinter `read_dense`, der
Import ist für sie in jedem Fall bezahlt; eine 2327-ms-Zwischenzahl bei
`subdivide_surface` war Fremdlast und fiel in zwei Wiederholungen). Der
Docstring des Schlüssels hatte den Auswahl-Fall untersucht und mit einer
Messung verworfen — die Messung war richtig und trug nur, solange kein
verzögerter Import im Spiel war; seit dem `deferred`-Umbau entscheidet die
Auswahl, wer den trimesh-Import bezahlt.

- [x] **Erledigt** (15/53, `d4cea5fd`, 30.08.2026): Der verzögerte
      Geometrieimport steht vor der Uhr und trägt seine eigene Marke
      `deferred_geometry` (solo 505/483 ms); `read_dense` misst seither
      in jedem Kontext dasselbe — solo 436/444 ms gegen 427–443 im
      Volllauf, vorher 1072 solo. Die Import-Verschiebung aus dem
      Kundenstart bleibt über die neue Marke messbar. Betriebsnotiz:
      Die frische Marke durchläuft je Maschine die dokumentierte
      MIN_RUNS-Delle — die ersten zwei Läufe sind bewusst blind.

---

## Der Startweg sammelt keine Einzelheiten (30.08.2026)

Der Installationsweg des Zusatzprogramme-Dialogs sammelt die Ausgabe der
Paketverwaltung in `_details` und blendet einen *Einzelheiten*-Knopf ein.
Der **Startweg** desselben Dialogs hat beides nicht: Scheitert ein
Dienststart, steht der Satz da (seit dem Adressen-Fix mit der Seite zum
Nachsehen), aber das Startprotokoll des Dienstes ist weg — genau die
Zeilen, mit denen jemand zum Support ginge.

- [x] Erledigt mit `eb64c90f` (30.08.2026): Der Startweg füllt die
      Einzelheiten mit Aufruf und Adresse — und der ungesuchte zweite
      Befund gleich mit: `_start_tool` räumt die Ausgabe des vorigen
      Vorgangs jetzt vor jedem Rückweg ab, statt die pip-Ausgabe der
      Installation unter *Details anzeigen* stehen zu lassen.

---

## Der Textweg nennt ein Modell, das kein Weg beschafft (30.08.2026)

Weg 3 aus Text: `missing_models("text_to_mesh")` meldet die Bildrolle —
TripoSG und BiRefNet liegen da, ein SDXL-Modell nicht. `comfy_setup`
richtet den Bildweg vollständig ein (7,5 GB TripoSG, 445 MB BiRefNet) und
den Textweg nicht, und keiner der sechs Punkte in `install.REQUIREMENTS`
bringt ein Bildmodell mit. Der Kunde liest die ehrliche Auskunft „ComfyUI
braucht ein SDXL-Modell unter models/checkpoints", drückt *Zusätzliche
Programme …* — und findet dort nichts dafür. Die Auskunft stimmt, der Weg
dahinter ist keiner (gemessen von 5d, unabhängig bestätigt von fb;
seit 5ds Erzeugen-Knopf-Fix ist der Knopf dabei gesperrt statt tot). Auf
dieser Maschine ist SDXL seit dem 30.08.2026 installiert und
`readiness("text_to_mesh")` steht auf ready — die Maschine kann den Weg,
das Produkt noch nicht. Der Weg selbst ist über das Fenster gefahren und
trägt vollständig (5d): „ein einfacher Becher" in 143 s (der Bildweg
braucht 15), vier Stapelschritte samt Provenienz, am Ende 150 000
Dreiecke, wasserdicht — die Dauer gehört mit in die Abwägung, denn sie
ist das zweite Argument neben den sieben Gigabyte.

- [x] **Gebaut und gelandet, am Code nachgemessen (30.08.2026):
      anleiten statt mitliefern**, wie Robert entschieden hat. Die eine
      Quelle sind die `IMAGE_MODEL_*`-Konstanten in `comfy_setup.py`
      (Repo, Ordner, Größe — nicht `SDXL_*`, eine Suche nach dem
      Markennamen findet sie nicht); `manual.py` erzeugt daraus die
      Seite „Welche Modelle Solidon benutzt" samt Tabelle und
      „Das Bildmodell selbst hinlegen", und der `NO_MODEL`-Satz im
      Erzeugungsdialog nennt Datei und Ordner aus derselben Quelle
      (`generate_dialog.py`, Kommentar dort belegt die Absicht). fb's
      Mitliefern-Hälfte ist entfallen.

---

## Eine Kundenanfrage aus dem Dentalbereich (30.08.2026)

Ein Kunde mit FDM- und Resindrucker — beruflich exocad und 3shape, privat
Fusion 360 und Solid Edge — hat vier Fragen geschickt: SpaceMouse,
Resin-Drucker, Lizenzmodell, Kaufen. Zwei davon beantwortet der Bestand
(ein Schlüssel für alle eigenen Rechner, genau einer aktiv; verkauft wird
ab dem 01.11.2026), zwei sind Arbeit. Die Anfrage liegt in Roberts
Postfach (R. W. D., Zeitz, 30.08.2026); der Antwortentwurf nennt beide
Punkte als notiert — was hier steht, ist also auch zugesagt.

- [~] **SpaceMouse-Anbindung: Konzept liegt vor**
      (`konzepte/konzept-3d-maus-2026-08.md`, 30.08.2026) — wartet auf
      Roberts Entscheidungen §12, zuvorderst Gerät und Reihenfolge gegen
      die Grundsteuerung. Empfehlung des Konzepts: bauen nach den neun
      Grundsteuerungs-Paketen, mit einem Gerät auf dem Tisch, und nur
      wenn die Abhängigkeit festschreibbar ist — fällt eine der drei
      Bedingungen, bleibt E10 stehen und der Kunde bekommt eine
      begründete Absage.
- [~] **Resin Stufe 1: entschieden und beratschlagt — bauen, als
      nächste Serie nach der Panels-Welle** (Freigabe + Konzept-Autorin
      15/53, 30.08.2026, nach Roberts Delegations-Order). Weg B
      (Verfahren im Druckerprofil), mit zwei beratschlagten
      Präzisierungen gegenüber dem Konzept: **zwei** generische
      Resin-Geräte im Startbestand (klein ~130×80, groß ~220×120 —
      die Bauraumfrage ist die häufigste Resin-Fehlerquelle, ein
      einzelnes Generikum beantwortete sie wieder still), und **B4
      wandert in Stufe 1** (die FDM-Regeln bekommen ihren
      Geltungsbereich sofort — sonst bekommt ein Resin-Profil weiter
      Brim-Ratschläge und die stille Vorgabe ist nur eine Ebene tiefer
      gerutscht). Cupping/Drains bleiben Stufe 2; der Dental-Kunde
      wird über die zugesagte Mail nach seinem Gerät gefragt. Ziel:
      0.2.3-Zyklus, Paketschnitt bei Serienstart.
- [ ] **Die Zusagen aus der Antwort — versendet, damit scharf.** Die Mail
      ging am 30.08.2026 um 11:24 von support@solidon3d.de hinaus; fällig
      sind jetzt die Nachricht zum Verkaufsstart (spätestens 01.11.2026)
      und das „Sie hören von mir", falls die SpaceMouse kommt.

Der Kunde hat noch am selben Vormittag geantwortet, und die Antwort
verschiebt den Resin-Punkt: Sein Bedarf ist **nicht** eine
Resin-Analyse, sondern die Vorbereitung nicht perfekter Dateien VOR dem
Hersteller-Slicer — viele Resin-Drucker arbeiten nur mit dem eigenen,
rudimentären Slicer, und die Lücke füllte bisher Meshmixer. Solidon als
Vorstufe („Datei rein, repariert und angepasst raus") ist für ihn die
Lösung; Resin-spezifische Prüfungen sind das Sahnehäubchen, nicht der
Kern. Das Resin-Konzept aus dem zweiten Kästchen beginnt darum bei
dieser Vorstufe, nicht bei Saugglocken. Die angekündigte PayPal-Spende
ist noch am selben Tag eingegangen (10 €) — die erste Einnahme des
Projekts —, und er will Solidon seinen Dentalkunden empfehlen — der
Multiplikator ist real, und „Meshmixer-Nachfolge im Dentalbereich" ist
ein Positionierungs-Datenpunkt fürs Marketing.

---

## Die ComfyUI-Modelle bekommen eine Auswahl (30.08.2026)

Roberts Auftrag im Anschluss an die Modell-Hinweise: „bei beiden auswahl
welches man nutzen wil". Beim Sprachmodell gibt es die Wahl (Combobox im
Chat-Dialog, gemerkt über `remember_ollama_model`); bei den
ComfyUI-Rollen entschied `_pick` allein über `MODEL_ROLES`.

- [x] **Gebaut, verifiziert und gelandet** (`17c4bebb`, 30.08.2026):
      `configured_model`/`remember_model` je Rolle in `mesh.py`
      (`MODEL_SETTING_PREFIX`, leer heißt automatisch — ohne Eintrag
      entscheidet weiter die Rollenauflösung, §2.4), `model_choices` im
      selben Graphendurchgang wie `missing_models`, Auswahlfelder im
      Erzeugungsdialog (`_fill_models`: Feld nur bei mindestens zwei
      Dateien und vorhandenem Titel, gemerkt wird **vor** dem Wurf),
      Tests und Katalogzeilen. Über das Go-Verfahren eingereicht und
      von der Freigabe vollständig gelesen.

---

## Der Download-Ordner sammelt jede je gebaute Fassung (30.08.2026)

Beim Aufräumen der Worktrees (Sitzung 50, Roberts Auftrag) fiel als
Nebenbefund `website/dl/` auf: **11 GB in 40 Dateien**, Pakete aller
Versionen ab 0.1.1. Angeboten werden im Download-Kasten stets nur die
vier Pakete der aktuellen Fassung; die Update-Prüfung zeigt ebenfalls
nur auf die neueste. Alles Ältere ist entweder ein bewusstes
Rollback-Archiv oder totes Gewicht — und was davon auch auf dem Server
liegt, ist bisher nicht gezählt.

- [ ] **Roberts Produktentscheidung:** alte Pakete behalten oder auf
      die angebotene Fassung eindampfen. Falls eindampfen: erst den
      Serverbestand zählen, dann lokal und oben in einem Zug räumen —
      und die Reihenfolge-Regel des Veröffentlichens gilt auch hier
      (nie löschen, worauf eine noch liegende `version.json` zeigt).

---

## Das Update-Fenster verliert die Gliederung auf dem Transport (30.08.2026)

Robert sah nach dem 0.2.2-Release die 56 Punkte im Update-Fenster als
flache Liste, während Website und Verlaufs-Dialog dieselben Punkte unter
`###`-Überschriften gliedern. Der Parser kennt `Entry.groups` seit
0.2.0, `changes_dialog.py` liest sie — nur `make_download` schreibt die
flache Sicht (`entry.points`) in die `version.json`, und das
Update-Fenster zeigt, was ankommt. Roberts Auftrag: „gleich abarbeiten
bzw verteilen und review".

- [ ] **d3 baut das Paket** (beauftragt 30.08.2026): `groups` je Sprache
      zusätzlich in die `version.json` (das flache `changes` bleibt für
      die Clients draußen), die Kappung kürzt beide Kopien synchron
      unter das 64-KB-Budget, `updates.Release` liest die Gruppen
      tolerant mit Herkunfts-Grenzen, der Dialog rendert sie in der
      Optik des Verlaufs-Dialogs, Tests je Zusage. Sichtbar wird die
      Gliederung beim Update **auf** die übernächste Fassung — der
      Dialog reist ja mit der App. Der Changelog-Punkt dazu entsteht
      erst beim 0.2.3-Zug, sonst zeigte die Website eine ungebaute
      Version. Review und Alt-Client-Messung (v0.2.1-Code gegen eine
      Datei mit `groups`-Feld) liegen bei der Freigabe.

---

## Die Grundsteuerung soll sich wie im Slicer anfühlen (30.08.2026)

Roberts Auftrag nach dem 0.2.2-Release: „steuerung für nicht cad kunden
einfach machen, verschieben, auswählen, rotieren, skalieren usw" —
sauber abarbeiten, verteilen, Review. Der Maßstab ist der Slicer, aus
dem diese Kunden kommen (ein Klick wählt, Move/Rotate/Scale sind je ein
Knopf mit Griffen am Körper), nicht ein CAD.

**Die Bestandsaufnahme ist da** (bedienlogik, 30.08.2026), und ihre
erste Auskunft ist eine gute: Der Slicer-Direktzug existiert längst
(Körper anklicken, ziehen — `827c3200`), der Griffsatz vereint alle
drei Gesten, und die Zahl während des Zugs kann kein Slicer. Elf
Hürden bleiben, geschnitten in neun Pakete; zwei Bedienfragen liegen
bei Robert (Zug ohne Vorauswahl; Ort der Zahlenfelder).

| Paket | Inhalt | Größe | Stand |
|---|---|---|---|
| P1 | Transformleiste wird Slicer-Leiste: drei Rollenknöpfe, Zahlenfelder je Rolle in der Leiste (Robert, 30.08.2026), „Gizmo"-Haken entfällt — das Werkzeug ist der Griff; `LengthSpin` zieht bei Einheitenwechsel auch in offenen Leisten nach; Fang-Menü hinter Raster-Symbol | M | **fertig** (`b43aab74`, d3; 391 Testzeilen, Handbuchabsatz nennt den Tipp-Weg) |
| P2 | Haken-Reste und Texte nachziehen | S | **gegenstandslos — durch P1 miterledigt, nicht geleistet** (d3, gemessen mit Gegenprobe: „Gizmo" steht 53-mal im Baum und null-mal in einem Kundentext — die 53 sind Fachsprache in Docstrings nach §18.11; `gizmoToggled` und `self.gizmo` sind nirgends mehr referenziert. P2 war geschnitten, bevor klar war, wie weit P1 reicht) |
| P3 | Mehrfachauswahl ehrlich: Zug bewegt nie still nur einen | S | **fertig** (`cb78bd58`): Zug bewegt alle Gewählten in einer Transaktion, die Statuszeile sagt es vorher; Drehen/Skalieren siehe P5 |
| P4 | ~~Zug ohne Vorauswahl~~ **entfällt** — Robert hat entschieden (30.08.2026): erst wählen, dann ziehen bleibt | — | zu |
| P5 | Mehrkörper-Drehen/Skalieren um den gemeinsamen Punkt | M | **fertig** (`d310f8fe`, Formatversion 18): `about="point"` mit genanntem Drehpunkt, das Fenster liefert die Mitte der gemeinsamen Hülle; der Anker entscheidet, nicht die Zahl (Null ist ein gültiger Punkt). **Der Versionssprung kam aus der Messung, nicht aus der Regel**: v0.2.2 nimmt den neuen Wert an und fällt still auf `centre` durch — rechnet also falsch statt abzulehnen; die plausible Vermutung („validate wirft") wäre falsch gewesen, der Wert kam dort nie an. Migration 17→18, `example_v18.p3d` eingecheckt, der zurückgezogene „gilt dem ersten"-Satz ist aus allen fünf Katalogen entfernt |
| P6 | Nach dem Drehen aufs Bett setzen (Haken, Vorgabe an, ein Undo) | S | frei (Reservierung aufgehoben) |
| P7 | Flächen-Gizmo beschriftet sich vor dem Zug | S | **fertig** (`d5eda37c`) — mit ehrlichem Umweg: Die erste Fassung schrieb den Namen an den Griff, und VTK nimmt in einem `vtkStringArray` nur ASCII — auf Französisch (`Face supérieure`, `Côté gauche` …) wäre das ein Kundenabsturz gewesen, den ein deutscher Torlauf nie sieht (gefunden d3, gegengeprüft 72). Jetzt: Marke am Griff, Name in der Statusleiste, ASCII-Wächter `test_nothing_on_the_gizmo_leaves_ascii` mit genau den vier Namen, Regel in `ansicht.md` |
| P8 | Verschieben/Drehen/Skalieren direkt im Kontextmenü | S | **fertig** (`fa694cf1`): 7 → 10 von 12 Zeilen, „Ändern" 30 → 27, Slicer-Reihenfolge und Grenze am gebauten Menü getestet, zwei Gegenproben gefallen |
| P9 | Aufeinanderfolgende Züge werden ein Verlaufsschritt | M | frei (Reservierung aufgehoben) |

- [ ] Die neun Pakete abarbeiten — je Paket Zahlen, Gegenproben und
      Review vor dem Commit; achsweises Skalieren bleibt bewusst
      hinten (verzerrt Bohrungen), die Bettebene beim Direktzug
      bleibt, und ein Bestätigungsdialog kommt nirgends dazu.

---

## Alle Panels und Dialoge aus Kundensicht (30.08.2026)

Roberts Auftrag nach der Steuerung: „alle panels und dialoge auch mal
sauber und gründlich durchgehen, optimieren und verifizieren aus
kundensicht wie immer" — mit dem vollen Leitsatz als Maßstab (Kunde
ohne CAD-Kenntnisse, einfach und schnell, hochwertig und
selbsterklärend, die Website als Sollliste).

Die **Bestandsaufnahme ist da** (bedienlogik, 30.08.2026, alles
gemessen statt geschätzt): Eine lange Nicht-anfassen-Liste (457 von
457 Parametern erklärt, 95 von 95 Hauptknöpfen unbeschnitten, die
leeren Zustände nennen den Weg heraus) und zwölf Befunde, geschnitten
in zwölf Pakete **D1–D12** (D, damit niemand sie mit den
Steuerungs-P verwechselt):

| Paket | Kern | Größe | Stand |
|---|---|---|---|
| D1 | Der Bericht zerlegt sein eigenes Bündel: `_resort`/`add_findings` bauen Zeilen ohne `_bundled` — jetzt ist `self._findings` die eine Quelle und `_rebuild()` baut jede Sicht daraus | S | **fertig** (`e833e938`, 72; Einzelheiten im Kästchen des Bericht-Abschnitts) |
| D2 | Speicherring gemessen: ein angeklickter Befund hielt das Fenster (10 von 10 überlebten) — `weak_slot` statt Lambda auf Fenster-Handlern, `_run_action` liest zur Klickzeit | S | **fertig** (`ad4c83f0`, 72) |
| D3 | Fehlerdialog und ComfyUI-Dialog haben keinen/den falschen Hauptknopf | S | offen |
| D4 | „Bohrung ändern" wählt still `hole_1` von vieren — `at_feature` nach vorn, plus Wächter „kein required-Parameter hinten" | S | **fertig** (`6c705a64`): Feld vorn, `_reason_locked` kennt „verlangt Merkmal, keines gewählt" (`labels.feature_requirement`), Register-Wächter steht; `paint_slot` als Zweitfall gemessen und korrekt frei |
| D5 | Leere Pflichtliste lässt den Hauptknopf aktiv — sperren und begründen, Grund aus `_needs_phrase` | M | offen |
| D6 | Die Kopfzeile verschwindet unter 2330 px Fensterbreite ins unbeschriftete Überlaufmenü — kürzen statt verschwinden | M | offen |
| D7 | Der Platzhalter-Wächter ist ASCII-blind: `{maß}` kann aus fünf Katalogen fallen, Test bleibt grün | S | **fertig** (`acbeffb3`): Regex auf Unicode, Mutationsprobe (`{maß}` aus en.json gelöscht) fiel rot | 
| D8 | Platzhalternamen vereinheitlichen (vier Namen für „Anzahl"), Doppelsatz „Knochen" zusammenlegen | M | nach D7 |
| D9 | Skelettleiste: Der Screenreader nannte die Pose, gemeint war der Knochen (eine Pose hat hier gar keinen Namen); zwei von drei Knöpfen sagten nicht, was sie tun. Der Test fragt jeden Knopf einzeln statt zu zählen — eine Zahl wäre beim vierten Knopf still wieder falsch | S | **fertig** (`be8b7f59`, 3a) — Katalog-Nachzug der zwei neuen Tooltips läuft |
| D10 | „Tokenbudget" im Chat ist kein Kundenwort — Zusammenfassung in Kundensprache, Zahlen unter Einzelheiten | S | offen |
| D11 | **Sechsundfünfzig Einstellungen, und jetzt eine Suche** — Suchfeld über der Klappe (wer sucht, weiß nicht, dass es dahinter liegt), heben statt filtern: Reiter wechselt, Klappe öffnet, Zeile rollt in den Blick und leuchtet, Zähler „2 von 4“, Eingabetaste führt weiter; gesucht über Titel, note-Satz und Gruppenname, Einheit bewusst draußen (träfe 22 von 56 Zeilen, gemessen). Zwei eigene Tests fielen der Mutationsprobe: einer grün gegen eine Teilzeichenkette („2“ in „1 von 2“), einer gegen einen erfundenen Beleg („Elefantenfuß“ kommt im Bestand nicht vor) — beide an gemessenen Wörtern neu gehängt. Stufe 2 (Slicer-Schlüssel als Suchaliase) bleibt offen | L | **fertig** (`bc3cbaf9`, 15/53) |
| D12 | **Vier Knöpfe hielten ihre Zeile fest, nach dem Muster, vor dem sie warnten.** Lambdas an Kind-Knöpfen fingen `self` — der Ring aus `wartezeit.md`, dieselbe Familie wie D2; jetzt gebundene Methoden, und der Lebensdauer-Test zählt die Zeile selbst statt des Dialogs, der auch mit Zombie-Zeilen starb | M | **fertig** (`1a04d00c`, 72) |
| D13 | Druckeinstellungen, drei Kleinfunde der Kundenfahrt — alle drei zu: Der Speichern-Knopf sagt, worauf er wartet (DR1, `705ffbd1`, 50); der Dialog wächst mit, wenn die Profil-Klappe nachgereicht aufgeht — `sizeHint` log mit 633 gegen 775, erst `layout().activate()` gibt die ehrliche Zahl (DR2); und statt Rollknöpfen, die unter dem Stylesheet blank sind (gemessen: 16×22 Punkte in einer Farbe, `image:` greift nicht), werden Reiter gekürzt statt abgeschnitten, voller Name im Tooltip, Dialog nimmt sich beim Aufklappen die Breite der Leiste (DR3) — DR2/DR3 in `5b7e4a46` (15/53), vier Mutationen je ein Glied rot | S | **fertig** — die Fahrt selbst war sonst ein Lob: Klappe öffnet sich selbst am richtigen Ort, Slicer-Wortschatz vorn, „Nichts einzuwenden." statt Leere |
| D14a | Roberts Order („materialauswahl und farbe sind sinnlos, da wir nach den filamenten gehen"): Das Farbfeld sollte fliegen — **die Messauflage fing, dass es nicht ersatzlos kann**: `slicer_keys.py:234/340` bildet es für beide Slicer-Familien ab, `handover.py:1285` überschreibt nur bei bemalter Spule — das Feld ist der Rückfall für den ungefärbten Fall, gestrichen verlöre der Slicer die Farbe. Die Kopfzeilen-Felder verschwinden trotzdem, aber mit der D14b-Ableitung statt ersatzlos. **Der Feld-Umzug ist gebaut** (`d5be5f58`): Das Feld verlässt die Vorderseite und heißt ehrlich „Farbe ohne eigene Spule", mit einem Satz, der die Rangfolge nennt; der alte Katalogsatz ist aus allen fünf Sprachen heraus | S | **fertig** (15/53) |
| D14b | Material und Farbe ergeben sich aus den Spulen des Projekts — Konzeptnotiz liegt vor und ist reviewt (`362fa679`, `konzepte/konzept-material-aus-dem-filament-2026-08.md`): Kopfzeile verliert Material-Combo und Farbfeld, `document.material` wird zum ehrlichen Rückfall, **keine Formatversion nötig** (nur die Herleitung ändert sich), fünf gemessene Abnahmepunkte. Entschieden beim Review: **der Drucker bleibt in der Kopfzeile** (ein Projekt hat einen Drucker, und Slicer-Kunden erwarten Drucker+Qualität oben). Die Slot-Frage ist am konkreten Fall entschieden (30.08.2026): **Slot 0 bestimmt die Toleranz**, nicht der größte Flächenanteil — die Hauskonvention sagt „Slot 0 ist das unbemalte Teil" (`oberflaeche.md`, `theme.slot_colour`), die Passung sitzt im Grundmaterial und nicht in der Dekoration (ein zu 60 % bemaltes Teil bohrt trotzdem ins Grundmaterial); gemessen am Zwei-Spulen-Fall Gehäuse-PETG/Schriftzug-PLA ist der Regelunterschied ohnehin ≤ 0,05 mm. Nebenbefund: Eine frische STL hat null Slots — der Weg-1-Normalfall läuft immer über den Projekt-Rückfall, ein Argument mehr für `document.material`. **Der Toleranz-Teil ist gebaut** (`5a3f764c`): `for_object` fragt die Spule, wenn am Körper nichts steht — Rangfolge Entscheidung vor Herleitung, Slot 0 über `spool.index == 0` statt Listenposition; die Mutationsprobe fand dort eine echte Lücke (Testliste hatte Slot 0 zufällig vorn), ein sechster Test mit umgekehrter Liste schließt sie. **Und die Kopfzeile wählt kein Material mehr, sie berichtet es** (`6e921f79`): mit Spulen die Materialarten („PETG + PLA"), ohne Spule „PLA — Projektvorgabe" mit Herkunft im Tooltip; „Filamente …" daneben klappt den Abschnitt auf und lässt ihn aufleuchten — Anzeige mit Weg. Kundenfahrt wiederholt: Vorderseite sieben Zeilen statt acht, ein Auswahlfeld weniger — kürzer, nicht nur anders. Eine Mutation fand einen Test, der am Weg vorbei prüfte (baute die Signalverbindung selbst); ein zweiter Test am Quelltext schließt die Hälfte | M | **fertig** (15/53) — Roberts Order komplett: `d5be5f58` + `5a3f764c` + `6e921f79` |

- [x] **Der Skeletteditor fängt nicht mehr bei null an** (`b3cfd578`, 3a;
      Roberts Entscheidung: „die einfachste variante für den kunden“ — keine
      neue Geste). Derselbe Editor, dieselbe Leiste, die Knochen sind schon
      da; „Fertig“ ändert denselben Schritt. Gelesen wird aus dem Dokument
      (aus einem gebeugten Körper lassen sich Knochen nicht zurückrechnen),
      der letzte Schritt gilt, ein unlesbares Skelett verweigert den Editor
      nicht (§2.1). `edit_operation` nimmt ein optionales `given` für Werte
      aus Gesten. Drei Tests, Mutation „der Editor lädt nichts“ rot.

Reihenfolge nach Kundenkontakt: D1, D2, D4, D5 (täglich) → D6, D3
(jedes Fenster, jeder Fehler) → D7, D9, D10 → D8, D12 → D11.

- [ ] Die zwölf Pakete abarbeiten — je Paket Zahlen, Gegenproben und
      Review vor dem Commit; die Fix-Details je Befund gibt die
      Freigabe bei der Beauftragung mit.

---

## Der Zeichenmodus und der Viewport bekommen ihre Durchsicht (30.08.2026)

Roberts Vervollständigung des Durchsichts-Auftrags: „den ganzen
zeichen modus am besten auch nochmal komplett durchgehen, sowie jedes
panel, dialog, viewport usw." Panels und Dialoge laufen als D1–D12;
was fehlte, sind der Skizzeneditor (4 800 Zeilen) und der Viewport mit
seinen acht Werkzeugen (8 200 Zeilen plus Leisten) — beide
Bestandsaufnahmen laufen mit derselben Drei-Fragen-Systematik
(versteht der Slicer-Kunde es ohne Handbuch; wirkt es hochwertig;
was ist getestet statt behauptet).

Die **Zeichenmodus-Bestandsaufnahme ist da** (bedienlogik, 30.08.2026,
fünf Messsonden am gebauten Fenster). Die guten Teile sind sehr gut
(Fangmarke, Bedingungssätze aus einer Quelle, Konfliktmarker); die
schweren Funde liegen an den Ausgängen und am Kernweg 2 — neun Pakete:

| Paket | Kern | Größe | Stand |
|---|---|---|---|
| Z1 | **Schwer**: Escape und „Verwerfen" vernichten die Zeichnung ohne Rückweg und ohne Ansage — die Formsitzung nebenan entscheidet umgekehrt („die teuerste Taste des Programms"). **Eine verworfene Zeichnung ist nicht mehr verloren.** `finish_sketch(keep=False)` las den Text nicht einmal, bevor es das Panel löschte — und ein Dialog davor ist durch Regel 19 ausgeschlossen, solange die Handlung rücknehmbar ist; sie war es nicht. Jetzt merkt sich das Fenster die Zeichnung samt Ebene als Editorzustand (`_DiscardedSketch`, Regel 2 — nie im Dokument gewesen), die Statuszeile nennt den Rückweg, `action_undo` holt sie zurück (dieselbe Kette wie `undo_sculpt_stroke`), und das Angebot verfällt, sobald der Verlauf weitergelaufen ist — sonst holte der Kunde nach drei Operationen die alte Zeichnung statt der Operation davor. Zwei Tests, zwei Gegenproben je eine Hälfte | M | **fertig** (`20838a37`, 50) |
| Z2 | **Ein Maß ändern ist ein Griff statt acht.** „Maß ändern …" im Kontextmenü der Bedingungsliste und auf Doppelklick; `change_constraint` schreibt die geänderte Liste in **einem** `_apply`, also einem Rückgängig-Schritt — Entfernen+Neusetzen wären zwei, und Strg+Z landete zwischen den Hälften. Der Eintrag erscheint nur bei Bedingungen mit Wert, gefragt am Eintrag statt an einer Artenliste. Zwei Tests, zwei Gegenproben; die erste fand einen Fehler im Test selbst (`hasattr` auf ein Feld, das anders heißt — die Zusage wurde still übersprungen). Nachzug aus V9: `oberflaeche.md` zählte acht Umschalter, es sind sieben (acht ist die Grenze); die „acht" in `manual.py`/`figures.py` meinen Füllmuster und waren richtig | M | **fertig** (`258999b6`, 50) |
| Z3 | **Die Taste galt niemandem.** Das Fenster graut „Wiederholen“ im Zeichenmodus aus und begründet das mit „gilt die Taste dem Werkzeug“ — für Rückgängig stimmt das (Strg+Z hängt am Panel), für Wiederholen kannte der Zeichenbereich die Taste nicht. Jetzt ein zweiter Stapel im Canvas (`undo` legt zurück, `redo` holt vor und legt seinerseits zurück, eine neue Änderung schließt den Zweig), `StandardKey.Redo` am Panel und ein Wiederholen-Knopf neben Rückgängig. **Den Knopf hat der Bestand erzwungen**, nicht der Entwurf: Nach dem Kürzel allein wurde `test_every_sketch_shortcut_is_named_somewhere_on_screen` rot — eine Belegung ohne sichtbares Ziel findet niemand (§19.2). Fünf Zusagen, vier Gegenproben, alle rot; eine davon fand eine Lücke (ohne sie kam man vor und nie wieder zurück). Das Symbol kommt aus `c1ccc90d` (72), auf den dieser Commit gewartet hat | S | **fertig** (`cc02754e`, 50) |
| Z4 | **Beide versprochenen Wege taten nichts, gemessen am gebauten Fenster.** Drei Punkte gesetzt, Eingabetaste, Doppelklick — danach null Elemente und drei offene Punkte. Die Empfänger (`mouseDoubleClickEvent`, `keyPressEvent`) sitzen im Zeichenbereich, und der ist im gefahrenen Modus unsichtbar. Der Ereignisfilter der Ansicht reicht beides jetzt an einen Rückruf weiter, nach dem Muster von `set_sketch_entry` (setzen beim Betreten, lösen beim Verlassen). **Der Rückruf sagt selbst, ob er zuständig war** — eine Eingabetaste ohne begonnenen Zug gehört weiter dem Maßfeld. Gemessen: Enter 0 → 1 Element, Doppelklick 1 → 2, ohne Zug bleibt es bei 2. Messfalle im Test festgehalten: Der erste Prüfstand sendete an das Viewport-Widget statt an den VTK-Interactor und meldete „wirkt nicht“; und jeder Weg braucht einen frischen Zug, sonst misst der zweite eine Lage, die der erste aufgelöst hat. Vier Zusagen, vier Gegenproben, alle rot | S | **fertig** (`d0a415af`, 50) |
| Z5 | Escape zweistufig: erst die laufende Kette abbrechen, dann das Werkzeug ablegen — macht den Hinweistext wahr und entschärft Esc-Esc | S | mit/nach Z1 |
| Z6 | Der Knopf heißt „Grundform", ist das Rechteckwerkzeug und versteckt das beste Anfänger-Angebot (sechs vollbemaßte Formen) hinter einem Pfeil | S | offen |
| Z7 | Der Kreis misst Radius, der Kunde denkt in Durchmesser (M3 → Ø3,2 getippt = Ø6,4 gedruckt): sofort „Radius" statt „Abstand" beschriften und „R" ans Maßfeld; die echte Ø-Bedingung im Kern ist der eigene Punkt darunter | S | offen |
| Z8 | **Zwei von drei Resten behoben, der dritte trifft nicht mehr zu.** (1) „Ansicht: freien Ansicht“: `plane_where()` liefert die **Dativform**, gebaut für „Sie sehen die Zeichnung aus der …“ — hinter einem Doppelpunkt steht sie im falschen Fall. Dabei fiel ein zweiter auf, den der Befund nicht nennt: Der Fallback trug „**der** gewählten Fläche“ mitsamt Artikel, im Ursprungssatz also „aus der der gewählten Fläche“. Eine Regel löst beides: **Der Artikel gehört in den Satz, nicht in die Wortliste** — „Blick aus der {view}“ und „gewählten Fläche“. (2) Tastenname im Katalogtext: Drei Stellen trugen „Entf“ im übersetzbaren Text (Kontextmenü, Bedingungsliste, Konflikt-Tooltip). Die Taste heißt „Del“, „Supr“, „Canc“ — die Übersetzer haben fünfmal richtig **geraten**, während die Bindung nebenan die Antwort kennt; jetzt `QKeySequence` mit `{key}`. (3) Schichthinweis zieht bei Ebenenwechsel nicht nach: **nicht reproduzierbar** (Messung 30.08.2026 abends) — er zieht in beiden Umgebungen nach, im Panel wie im Tooltip des gefahrenen Modus, mit zwei Fassungen für parallel und quer. Fünf Katalogschlüssel tot, vier neu, zwei Tests nachgezogen | S | **fertig** (`c36241c8`, 50) |
| Z9 | Zwei Zeichenumgebungen für dieselbe Aufgabe: Wer aus dem Verlauf korrigiert, landet im weißen 2D-Dialog statt im Viewport-Modus — der Feldweg führt künftig ins Fenster, der Dialog bleibt Rückfall | L | nach Z1 |

- [ ] Die neun Z-Pakete abarbeiten — Z1 zuerst; je Paket Zahlen,
      Gegenproben und Review vor dem Commit.
- [ ] **Ø-Bedingung im Kern** (aus Z7, Variante b): eine echte
      Durchmesser-Bedingungsart in `sketch/solver.py` samt Feld,
      Beschriftung und Migration — die Sprache des Druckers bis in die
      Projektdatei. Eigene Entscheidung mit Formatblick, nicht
      nebenbei.
- [x] **Abtragen an eingelesenen Netzen** (Robert, 30.08.2026: „abtragen
      auch an importierten netzen, mach es vollständig komplett und
      sauber"). `sketch_pocket` verlangte einen exakten Körper und
      antwortete sonst „Der gewählte Körper besteht bereits aus festen
      Dreiecken" — damit war der **häufigste aller Fälle** ausgeschlossen:
      Wer ein Modell herunterlädt, hat ein Netz, und in Fusion schneidet
      man hinein. Neu ist `geom/sketch_solid.py` (Umriss abtasten, senkrecht
      aufziehen, auf die Ebene drehen, 72 Ecken je Kreis mit begründeter
      Sehnenhöhe); `sketch_pocket` bekam eine Weiche und rechnet über die
      Boolesche Rückfallkette, `requires_kind="brep"` ist gefallen. In der
      Oberfläche fielen zwei Sperren: `_body_under_the_outline` sprang über
      jedes Netz hinweg, `_pocket_target_problem` sagte ab. Gemessen:
      144,0 mm³ an einem 40×30×10-Netz (6×6×4), durchgehend 80,0 mm³, und
      **auch ohne den optionalen B-Rep-Kern** — eigener Prozess mit
      gesperrtem `OCP`, weil die Gruppe optional ist (§30). Vierzehn Tests,
      vier Gegenproben, alle vier rot. Der Testfehler unterwegs ist die
      Lehre wert: Der Prüfquader lag von 0 bis 40, `shapes.rectangle`
      zentriert im Ursprung — gemessen 36 statt 144, und der Code hatte
      recht. Nebenwirkung, nachgemessen und dabei präzisiert: Die heutige
      `puppenhaus_fertig.p3d` hat die Reihenfolge längst getauscht und
      schnitt schon vorher exakt — es ist die Fassung daneben
      (`…p3d.vor-reparatur`, aushöhlen *dann* Taschen), die jetzt heil ist:
      alle sechs Schritte durchgelaufen, kein `stopped_at`, und die drei
      Taschen tragen 11 778,4 mm³ aus dem ausgehöhlten Netz ab. Wer ein
      altes Projekt mit dieser Reihenfolge öffnet, bekommt es also jetzt
      gerechnet.
Zulieferung an 3a, übergeben und dort weitergeführt (Kipp-Abschnitt):
Bei frei gekippter Kamera steht `view_plane` auf FREE_VIEW,
`_sketch_pull_offer` vergleicht gegen `sketch.plane` und bewirbt den
Ziehgriff, während weiter gezeichnet wird — Zeichenklick und Ziehgriff
überlappen genau in der Lage, die die Regel vermeiden wollte (gemessen,
Rechteck geschlossen: '' → 'ready' nach dem Kippen).
Die **Viewport-Bestandsaufnahme ist da** (bedienlogik, 30.08.2026, im
echten Fenster gefahren, acht Belegbilder im Scratchpad). Kernsatz:
Die Ansicht selbst ist gut — Auswahltiefe, Bohrungs-Zielhilfe,
Schatten, Zeigerrangfolge sind sorgfältig gebaut; was fehlt, liegt an
den **Übergängen**: Vier der sieben Werkzeuge lassen den Kunden im
ersten Moment nach dem Öffnen raten. Neun Pakete:

| Paket | Kern | Größe | Stand |
|---|---|---|---|
| V1 | **Der Schnitt öffnet nicht mehr auf ein leeres Bild.** `_apply_range` zentrierte nur, wenn der alte Wert *außerhalb* der neuen Spanne lag — bei einem Teil auf dem Bett (z ∈ [0, h]) liegt 0,0 immer darin; der Kommentar über der Zeile beschrieb die richtige Regel bereits vollständig. Jetzt zentriert der Achswechsel immer (`_axis_changed` reicht es als Parameter weiter, weil jeder Weg zur Achse über `currentIndexChanged` läuft); `set_ranges` behält die alte Prüfung, damit ein neu geladenes Teil den Regler nicht verschiebt. Zwei Tests über `plane()`, zwei Mutationen in beide Richtungen | S | **fertig** (`7d46a87f`, 50) |
| V2 | **Der Zeiger beim Körperzug stimmt wieder** — der Ein-Zeichen-Fix (`"moving"`→`"move"`) ritt im Dateistand von `edfb89b9` mit (Zurechnung geklärt, 3a führt ihn nicht als ihren); der Wächter dazu ist `d91798b3`: AST über die Call-Argumente von `set_drag_cursor`/`cursor`/`_tell` **und** die Return-Literale von `_resting_role` (auch unter ternären Ausdrücken — er fing beim Bau prompt seine eigene Sammellücke), beide Richtungen mutiert | S | **fertig** (`edfb89b9`/`d91798b3`, 72) |
| V3 | **Zwei Schemata hielten ihren eigenen Namen nicht** — und der Kernbefund war größer: Die mittlere Maustaste hatte gar keinen Beobachter, VTKs Basisverhalten schob. Jetzt ist die Zuordnung eine reine Tabelle (`_NAVIGATION` + `navigation_action()`, testbar ohne Fenster — genau deshalb konnte der falsche Satz zwei Schemata lang stehen: die VTK-Tastenkette lief offscreen nie); `cad` = Mitte dreht, Umschalt+Mitte schiebt, links wählt; `blender` = links wählt, Mitte dreht; `slicer`/`orbit` unverändert (eigens geprüft, dass der neue Beobachter ihnen das Schieben nicht nimmt). Dialog- und Menütexte sagen dasselbe wie der Code, das Handbuch verliert den seit je falschen Satz „rechte oder mittlere dreht"; drei Tests, vier Mutationsproben, ein Beinahe-Fehlbefund als Warnung im Testdocstring (Klick ohne Zug geht an `on_pick`) | M | **fertig** (`60e89828`, 72) — danach V6 |
| V4 | **„Schichten" tut ohne Auswahl nicht mehr stumm nichts.** Bei genau einem Körper nimmt das Werkzeug diesen (`_only_body()`) — nach dem Öffnen der Normalfall, und eine Frage mit nur einer möglichen Antwort ist keine; bei mehreren steht der Grund in der Leiste (`LayerBar.show_note()` nach dem Vorbild von `MapLegend.note`), aufs Teil zeigend statt auf den Baum. Regler und Hinweis schließen einander aus. Zwei Tests, zwei Gegenproben je eine Hälfte | S | **fertig** (`4c584b51`, 50) |
| V5 | **Das Messen endet nicht mehr wortlos**: drei `measurementStatus.emit` im Ton des Winkel-Pfads (§2.7) — Danebenklicken, keine Wandstärke messbar, erster Punkt gewählt; Katalogeinträge in allen fünf Sprachen mit den Bestandsbegriffen, Test misst am Signal, drei Emit-Mutationen einzeln rot | S | **fertig** (`e7cbbfbe`, 72) |
| V6 | **Nachgemessen lag es schwerer als notiert**: Der Flug-ohne-Marke-Fall tritt an 0 von 58 Befunden auf — die `op.*`-Fehler haben weder Ort noch Karte (`evaluate.py:1644` setzt keines von beiden), und ein Klick auf sie tut **gar nichts**; dazu acht folgenlose Info-Zeilen. Beschlossener Schnitt (3a): Die Zusage heißt **ein Klick auf einen Befund bleibt nie folgenlos**, dreistufig — (1) mit Ort: fliegen plus vergänglicher Ring (`_ring_points` liegt bereit); (2) ohne Ort, mit Objekt: auswählen und einpassen — die Marke, die ohne Ort möglich ist; (3) mit `op_id` (jeder Operationsfehler): zusätzlich den Verlaufsschritt hervorheben — die Antwort auf „welcher Schritt war es?" | M | **3a, im Bau** — Stufe 1 zuerst, 2 und 3 nach Messung am Fenster |
| V7 | **Der Schnittzeiger ist ausgebaut** — er war gezeichnet und wurde nie gesetzt (der Schnitt hat keine Klickgeste, seine Ebene wird an der Leiste gezogen); an der Stelle steht jetzt der Vermerk, `ansicht.md` kennzeichnet die Silhouetten-Lehre historisch und trägt den neuen Punkt „Eine gezeichnete Rolle braucht eine Setzstelle", den der V2-Wächter erzwingt | S | **fertig** (`d91798b3`, 72) |
| V8 | **Fertig, und der Befund war ein anderer als vermutet** (`f1ed8050`): Nicht die Fensterbreite macht das Panel hoch, das Werkzeug tut es — der umbruchfähige Hinweis verlangte im sizeHint nie seine Einzeilen-Breite, die Karte gab ihm nur den Wunsch, und Trennen stand auf 130 Punkten, wo 115 reichen. Jetzt verlangt der Streifen das Volle und gibt bei echter Enge nach (eigener Rückweg-Test). Alle Hinweise einzeilig, jedes Werkzeug 15–35 Punkte niedriger (de/fr/it identisch). Die Endzahlen über sechs Sprachen: Die breiteste Leiste verlangt 887 (transform, fr), der breiteste **Hinweis** 898 — der Hinweis ist das bestimmende Maß fürs Panel. **Der bauartbedingte Rest-Sprung (80–115 je Werkzeug) bleibt, entschieden**: Ihn glattzuziehen hieße, allen Werkzeugen die Höhe des zweizeiligen Trennen-Aufbaus zu geben — ständig höher gegen selteneres Umschalt-Springen, und niedrig schlägt konstant. Die Vergleichs-Lehre (zwei Läufe sind nur vergleichbar, wenn sie sich in genau einer Sache unterscheiden) steht in `24e20d7a` | S | **fertig** (d3) |
| V9 | Der `start=`-Test steht (`tests/test_tool_strip.py`, 137 Zeilen): kein Werkzeug öffnet ohne Bedienung und ohne Satz, und die Werkzeugliste der Datei stimmt mit dem Fenster überein — Gegenprobe gültig. **Die Auftragsannahme „hätte V1 und V4 gefangen" ist dabei gemessen gefallen**: V1 war kein Anschlagsproblem (der Regler bekommt einen Rand, 0 liegt bei einem 0–8-Teil zwischen −1 und 9 — der Fehler war „außerhalb des Teils", was nur der Leisten-Fütterer kennt, und `test_section_bar.py` prüft genau das über `plane()`), und die V4-Lage stellt die Datei nicht her. Zwei schwächere Zweit-Zusicherungen wurden bewusst nicht gebaut — sie wären grün geblieben, wenn man den Fehler wieder einbaut. Eine erste Gegenprobe war selbst ungültig (der Code nahm die Mutation zurück) und wurde erkannt | S | Test **fertig** (`2236ac3b`, 50); der Doku-Teil (Regeltexte: acht Werkzeuge, es sind sieben) läuft als Nachzug mit Z2 |

- [ ] Die neun V-Pakete abarbeiten — je Paket Zahlen, Gegenproben und
      Review vor dem Commit.

---

## Aufziehen und Absenken sollen auch gekippt präzise sein (30.08.2026)

Roberts Auftrag: „im zeichenmodus das aufziehen, abziehen noch besser
machen, wenn ein kunde zb manuell kippt und nicht auf seiten oder
vorderansicht geht." Der Kunde, der die Kamera frei gedreht hat, zieht
eine Skizze zum Körper auf — und die Zugrichtung (senkrecht zur
Zeichenebene) liegt dann schräg im Bild: Wie gut die Geste dort trifft,
was er meint, ist zu erheben und zu verbessern.

Der erste Teil ist gefallen, und Robert hat den Weg selbst gesetzt
(direkt an 3a, 30.08.2026): „die seitenansicht, vorderansicht und
draufsicht sollten in der nähe einrasten." 3a's Messung dazu: Nahe der
Draufsicht bedeuten zehn Pixel Mausbewegung bei 1° Kippung rund 70 mm
Höhe (Faktor 57 zur Seitenansicht), und die einzige Grenze im Code war
eine numerische (0,057°). Das Einrasten mit 10° Fangbereich gab es im
Skizzenmodus bereits und deckt den unbrauchbaren Bereich (< ~7°,
hergeleitet) vollständig — **`edfb89b9` baut es auch am Modell**: sechs
Achsenansichten (`iso` bewusst nicht — die schräge Ansicht liegt mitten
im Drehraum), gemeinsamer Unterbau `_nearest_view`, vier Tests mit zwei
greifenden Gegenproben (iso aufgenommen → Ausnahme-Test rot; Fangbereich
auf 5° gesenkt → Deckungs-Test rot). Keine zweite Schwelle neben dem
Einrasten — der `axis_hit`-Kommentar behält recht.

Die Fensterrand-Frage ist gemessen und zu (3a, 30.08.2026, echtes
Fenster, maximiert): `EndInteractionEvent` feuert auch beim Loslassen
außerhalb (oben, links, weit unterhalb), und die Kamera rastet in
jedem Fall exakt ein — die Schwung-Geste über den Rand landet nicht in
der unbrauchbaren Lage. Der Weg dorthin brauchte vier Anläufe, und der
**Kontrollfall (Loslassen innerhalb) fing jeden einzelnen**: winziger
Interactor ohne Projekt, Qt-Ereignisse statt VTK, Griff in der
Bildmitte (Auswahl statt Drehung) und waagerechter Zug, falsche
Maustaste im Slicer-Schema. Ohne Kontrolle wäre viermal in Folge eine
perfekt aussehende Bestätigung der Lücke herausgekommen — der Fall
geht als Beleg in `sondenbau.md`.

Die Fusion-Gegenmessung ist begründet entfallen (Entscheidung mit
Freigabe, 30.08.2026): Fusion klickt Ansichten am ViewCube an, ein
Fangbereich beim freien Drehen ist dort nicht bekannt — der Vergleich
hätte „nicht vergleichbar" ergeben. Stattdessen ist gemessen, **was der
Fangbereich den Kunden kostet**: Unter 10° Kippung sieht man an einem
40-mm-Teil 6,9 mm Bauhöhe (17 %) — praktisch eine Draufsicht, die
niemand absichtlich hält; bei 15° schon ein Viertel, das wäre eine
gewollte Schrägansicht. Die 10° liegen damit zwischen zwei Grenzen aus
der Sache: über 7° (ein Pixel je Rasterschritt) und unter 15°
(brauchbare Schräge). Die Zahl trägt aus eigener Herleitung.

Der Ziehgriff selbst ist repariert (`b3801e4b`): Bei gekippter Kamera
war er kürzer als seine eigene Trefferzone — er wächst jetzt längs mit
der Perspektive, ohne quer aufzublähen (eigener Test für beide
Richtungen). Und der Zug ist **gemessen, im echten Fenster, vom Fuß
des Griffs** (erster Aufbau maß von der Bildmitte und fand 115 mm ohne
Mausbewegung — das war der Abstand zur Achse, nicht der Zug; der
Kontrollfall am Fuß gibt ~0): Bei 10° Kippung bedeuten zehn Pixel
10,3 mm (1,2 Pixel je Rasterschritt — die hergeleitete Grenze, am
Fall bestätigt), ab 15° ist es komfortabel (2,2 px/Schritt), bei 45°
präzise (8,5). **Das Einrasten deckt den unbedienbaren Bereich ab;
der Zug selbst braucht keine Änderung** — gemessen, nicht gebaut,
damit etwas gebaut ist.

- [x] **Der Zug zeigt seine Zahl** — gemessen im echten Fenster mit
      echtem Zug bei 10/20/45/90° („gesetzt heißt nicht gezeigt"),
      nicht am Code. Vier Eigenschaften über „eine Zahl ist da"
      hinaus: Sie folgt dem Zeiger (dieselbe Leiste wie beim Bewegen),
      sagt die Richtung als Wort („Höhe"/„Tiefe" — zweite Kodierung
      neben dem Vorzeichen, Regel 18), zeigt den gefangenen Wert
      statt des Rohmaßes (der Kunde sieht 12,00 und bekommt 12,00)
      und steht in der Anzeigeeinheit bei Millimeter-Kern. Getippt
      übernimmt die erste Ziffer den Zug, ohne Fang — wer tippt,
      meint es exakt.

**Damit ist das Kipp-Gebiet vollständig** (30.08.2026): Die Kamera
landet nie in der unbrauchbaren Lage (`edfb89b9`), der Griff ist bei
jedem Winkel sichtbar und greifbar (`b3801e4b`), und der Zug ist
bedienbar und zeigt seine Zahl — gemessen, keine Änderung nötig.

Parallel zur Aufnahme ist der **Erststart** bereits gefahren (15/53 im
echten Fenster, Belegbilder) und in einer Hand (50). Erledigt daraus:

- [x] **Der Startbildschirm nutzt die Breite, die er sich selbst
      erlaubt** (50, `654fb940`; unabhängig auch von 15's Fahrt als
      FR8 belegt) — er blieb bei 714 Pixeln auf jeder Fensterbreite
      von 1280 bis 3413: `setMaximumWidth` erlaubt nur, und die Spalte
      saß ohne eigenen Dehnfaktor zwischen zwei Stretch-Feldern. Der
      bestehende Test prüfte die Rechnung (`_columns == 3`) und war
      grün, während seine eigene Assert-Meldung („die Breite ist da
      und wird nicht benutzt") wörtlich eintrat; der neue misst die
      Wirkung, Gegenprobe ohne Dehnung fällt. FR6 (gestrichelter
      Fokusring) fiel beim Nachmessen: Roberts eigene
      Review-Entscheidung vom 25.08. mit dreifach getesteter
      Regel-18-Kette — kein Befund. FR1 ist Resin-Konzept-Stufe-1.

- [x] **Der Erststart lässt den Kunden an vier Stellen nicht mehr
      raten** (50, `c06de19e` — FR3/FR4/FR5/FR7 aus der Bedienfahrt).
      Unter dem Druckerfeld steht der Ausweg für ein Gerät, das nicht
      in der Liste ist; die Platzhalter benennen, worauf sie warten
      („Zusatzprogramme — wird nachgesehen …"), womit auch der Grund
      für den kurz gesperrten Knopf direkt darüber steht — der
      Grundsatz „kein Knopf auf eine Vermutung" blieb unangetastet,
      verteidigt von seinem eigenen Test. Die doppelnde Zusammenfassung
      trägt nur noch den Scheiter-Fall; Waisen (Feld, Funktion, Import,
      zwei Katalogzeilen) sind mit heraus. Test misst am gebauten
      Dialog vor der Erhebung und verlangt, dass zwei Platzhalter nie
      gleich lauten; vier Gegenproben, je ein Befund zurückgedreht,
      fallen einzeln.

---

## Design und Anmutung bekommen ihre eigene Durchsicht (30.08.2026)

Roberts Frage („die panels und dialoge wurden jetzt alle mal gründlich
geprüft auf design, layout, modern, innovativ, übersichtlichkeit?")
deckte auf: Die D-Serie prüfte Funktion und Bedienung — die visuelle
Achse war nur Beifang. Die Erhebung ist gefahren (echte Qt-Plattform,
beide Themen, Deutsch und Französisch, Arbeits- und Leerzustände, 158
Belegbilder) und liegt vollständig in
`konzepte/durchsicht-design-2026-08.md`: **40 Befunde, sechs davon
kritisch.** Die stärksten Stellen: Startbildschirm, Kürzelfenster,
Symbolsatz. Die schwächsten: Bausteinkatalog, Skizzenkarte, Menüleiste.
Roberts zweiter Sichtbefund („bei den parametern sind die eingabefelder
jetzt manchmal zu klein") ist behoben (`1f25be4a`, 15) — **und die
Verdachtskette der Freigabe fiel an der Messung**: Weder die verbreiterten
Spinbox-Knöpfe noch das Einheiten-Suffix waren die Ursache (der Deckel lag
mit 173 weit über dem Wunsch von 149), sondern der fehlende **Boden**: Die
Felder tragen `SizePolicy.Ignored`, damit ihr Wertebereich nicht die Breite
diktiert — und schrumpften damit unter das Maß ihrer aktuellen Zahl (92
gemessen, 118 nötig; „2,4" statt „2,40", stumm geschnitten).
`least_number_width` rechnet den Boden aus dem heutigen Text plus einer
Ziffer Reserve; dieselbe Lücke im Operationsdialog ist mitgefixt (dort
blieb genau ein Punkt Luft). Zwei Nicht-Bauten, beide gemessen: das
Einheitenfeld misst sich schon, der Druckdialog hat implizit einen Boden.
Roberts erster Sichtbefund („Fertig steht zweimal da") ist zu
(`f15b91a4`, 50): Keine Leiste nennt den Knopf mehr im Hinweis daneben
(Gegenrichtungs-grep leer), und die Ersatztexte sagen nach Roberts
Direktkorrektur, was als Nächstes **geschieht**, nicht was der Modus
**ist** — „daraus wird jetzt ein Körper" statt einer Modusbeschreibung.

| Paket | Kern | Größe | Stand |
|---|---|---|---|
| G1 | **Jede Menü-Überschrift ist jetzt sichtbar** — die Ursache war der Windows-Stil, nicht das Stylesheet (gemessen, sechs Varianten wirkungslos): `menu_heading()` setzt die Kategorie als Label in einer `QWidgetAction`, und `setSeparator(True)` hält sie aus der Zwölf-Zeilen-Rechnung des §35 heraus (zwei gezählte Zeilen statt drei); am echten Menü „Erzeugen“ vier Überschriften, elf gezählte Zeilen wie zuvor, 2788 statt 2498 helle Punkte. Der grüne Wächter, der es hätte fangen müssen, prüfte `action.text()` — gesetzt, nie gezeigt; er verlangt jetzt ein sichtbares Label je Titel und meldet den Rückbau wortgenau (B1) | S | **fertig** (`cda48d29`, 72) |
| G2 | **Kritisch**: Die Prozentzahl im Fortschrittsbalken ist ab der Hälfte unlesbar — Kontrast 1,69 auf dem Bernstein-Chunk im dunklen Thema (B2) | S | **gegenstandslos, gemessen** (72): kein Balken der Anwendung zeigt Text — alle sieben rufen `setTextVisible(False)`, der Wächter dafür existiert; der Befund maß ein Widget, das es so nicht gibt. Methodennotiz im Dokument |
| G3 | **Kritisch**: Der waagerechte Rollbalkengriff wird zur 2-Pixel-Linie — `min-width` fehlt (B3) | S | **fertig** (`fcf4e291`, 72): `min-width` neben `min-height`, Griff 2 px → 16 px; „der Befund braucht seine eigene Größenordnung“ steht im Testdocstring |
| G4 | **Komplett zu.** B4: Platzhalter von der ersten Millisekunde (`482a3aac`), Balken begründet abgelehnt. B25 gemessen zerlegt: Normierung war da, Grundlinien mit dem Platzhalter zu, Ruheform bei 72 (style.py); die Umbruchlöcher fielen an der Nachmessung mit tragfähigem Aufbau (die erste Sonde nahm eine Gruppenüberschrift als Reihenreferenz) — senkrecht konstant 43 px (der Platz der Überschrift, kein Loch), waagerecht ist der Leerstand die Natur des Gruppenrasters wie in jedem Dateimanager. **Mitwachsende Kacheln: entschieden nein** — die Vorschauen sind auf feste Größe gerendert und würden unscharf skalieren oder Mehrfach-Renderings erzwingen, und der Leerstand betrifft nur dünne Gruppen; kein Kundengewinn, der die Kosten trägt | M | **fertig** (3a) |
| G5 | **Der Grund gegen ein größeres Bild war abgelaufen.** Der Docstring von `_preview_pixels` begründete den Faktor 1,2 damit, dass ab 1,7 der Name gekürzt werde — gemessen bleibt die Spalte „Objekt" bei 19, 32, 40 und 48 Punkten Vorschau konstant 165 breit, und `elidedText` kürzt in keinem der vier Fälle. (Die 260 Punkte Kartenbreite darin stimmen dagegen: Meine Gegenmessung mit 418 war ein maximiertes Fenster, mein Fehler.) Jetzt Zeilenhöhe mal 2,5 — 40 statt 19 Punkte, Untergrenze 40, Deckel 56 (ein Drittel der Spalte). Die Zahl entscheiden die Belegbilder: bei 40 ist die Platte als Körper mit Kante und Schattierung erkennbar, bei 32 knapper, bei 19 gar nicht. Preis im Docstring genannt, weil er echt ist: Zeile 44 statt 23 Punkte hoch. Ein Test mit drei Zusagen, drei Gegenproben, alle rot | S | **fertig** (`8f994e4c`, 50) |
| G6 | **Notiz liegt vor und ist reviewt** (`9714dabe`, `konzepte/konzept-akzentfarben-haushalt-2026-08.md`): Bernstein trägt neun Bedeutungen, vier leuchten ohne Anlass. Die Trennlinie ist **flüchtig gegen dauerhaft** (beim Review übernommen — sie erklärt auch die Grenzfälle Fortschritt und aktives Werkzeug ohne Ausnahme): Der Akzent gehört dem Flüchtigen und genau einem Dauerhaften, dem Hauptknopf — der auch gesperrt sichtbar bleibt, und „Schließen“ ist nie einer. Leiser: aktives Werkzeug (gedämpfte Fläche), Kartenkanten (Linienfarbe). Eigene Farbe: Ablaufdatum → Warnung, „nimmt Material weg“ → Rollenfarbe. B16 ist zu (`b743bdb1` — gemessen stand der dringlichste Befund in der schwächsten Schrift des Fensters: Rot 4,52 gegen 13,59 für Fließtext; die Symbolform trug den Schweregrad schon, die Rollenfarbe reist jetzt als Wert an der Zeile, prüfbar ohne zu zeichnen). Wächter: höchstens ein Akzent-Element im Ruhezustand, am echten Fenster. Umsetzung in Teilen: Kartenkanten sind zu (`ffb76529`: Umfragekarte auf Linienfarbe; die Startkachel-Kante bleibt — sie steht nur unter dem Zeiger und ist damit flüchtig, die eigene Trennlinie schlug die pauschale Vorgabe), Katalogfarbe war schon eigen (#d19e57 ≠ Akzent, gemessen); Ablaufdatum-Warnfarbe mit G10 (72), Die Werkzeug-Dämpfung ist zu (`04fc6968` — und beim Messen wurde mehr daraus: Im hellen Thema riss der aktive Knopf die 3,0 aus WCAG 1.4.11 an keiner Stelle, Kante und Fläche lagen bei 1,70; jetzt Kante 3,01 über `accent_line`, gedämpfte Fläche leiser als jeder Rahmen und trotzdem das einzige bunte Feld. `_recolour` fiel ersatzlos — die Themenschrift bringt am Symbol 4,93 statt 2,72 —, und der aktive Knopf antwortet erstmals beim Überfahren. Zwei isolierte Gegenproben, Rückbau byteweise. Dazu heilte `ec58c62e` zwei main-rote Verlaufstests aus der eigenen B31-Zusagen-Änderung). B22 ist zu (`4d83b1ca` — sieben Dialoge bekommen ihren Hauptknopf ausdrücklich, drei Anzeigefenster verlieren ihren; `style.no_primary` steht jetzt als Gegenstück neben `make_primary`. **Der Fenster-Wächter fand beim ersten Lauf einen zehnten Fall, den die Handmessung nicht bauen konnte** — der Kalibrierungsdialog fiel wegen eines Pflicht-Arguments aus dem Prüfstand; die Überlegenheit über den Quelltext-Wächter ist damit beim ersten Einsatz bewiesen). Der Fund dahinter: **Qt vergibt den Default von selbst** — neun Dialoge trugen einen stillen Hauptknopf mit Farbe, aber ohne die halbfette Zweitkodierung (Regel 18 an neun Stellen), „Schließen" war in drei Fenstern akzentuiert, und der Quelltext-Wächter war strukturell blind (setDefault ruft niemand). Vier der sieben Durchsichts-Dialoge waren längst richtig. Bau: make_primary an sechs handelnde Knöpfe, setAutoDefault(False) an den drei Schließen-Fällen, neuer Wächter am gezeigten Fenster. **Entschieden: Ein reines Anzeigefenster hat keinen Hauptknopf** — der Akzent lädt zur Handlung ein, und Schließen ist keine; die Präzisierung steht in der Notiz. Danach offen: Ablaufdatum-Warnfarbe mit B26 (72), Ruhezustands-Wächter (d3, erst wenn Dämpfung und B26 gelandet sind — vorher wäre er bei Geburt rot) | L | **in Umsetzung, verteilt** |
| G7 | Widget-Grundformen in `style.py`: Slider ungestylt, Spinbox-Pfeile 10×11 mit verdecktem Trennstrich, Splitter-Fuge Kontrast 1,0, gesperrte Zustände kaum unterscheidbar, Werkzeugknopf rahmenlos (B7/B15/B30/B32/B37) | M | **72, läuft** — Teil 1 fertig (`5adc63f7`): der Regler hat als letztes Bedienelement seine Form, am Einbauort gemessen (trug in beiden Themen dieselben 21 Qt-Vorgabefarben); alle Zustände inklusive gesperrt, drei Regler hängen daran. die Splitter-Fuge ist zu (`3a789db0`) und Zahlenfeld/Combobox auch (`b220ea78`: Knöpfe vier Punkte breiter und ins Innere gerückt, Pfeilfeld mit Radien — dabei fing der geschärfte Wächter, dass Qt bei eigener ::drop-down-Regel den Pfeil nicht mehr zeichnet, und verlangt jetzt von jedem gestalteten Pfeil sein Bild). und B32/B37 sind nachgeliefert (`6c1b28ee`: der Werkzeugknopf trägt die Zebrafarbe als leise Ruhekante — wer keine will, sagt es ausdrücklich; Kästchen und Text gesperrter Ankreuzfelder fallen zusammen auf die Sperrfarbe, vorher verblasste nur der Text). **Das Bündel ist komplett** — mit einer Nachbesserung: Die erste Ruhekante (Zebrafarbe) war gesetzt und unsichtbar (1,13/1,01), von 15 am gerenderten Knopf gefangen; `5f9fdcc6` legt sie auf die Linienfarbe (2,30/2,00), der Test nennt beim Rückbau die Zahlen |
| G8 | **Formular-Raster: zu.** Der Rasterteil legte alle Beschriftungen eines Dialogs auf die breiteste (`b0a25328`, nur sichtbare Zeilen — der Prüfstand zählte erst Phantome); B36 ist gebaut (`aa354f7c`): Die Regel fragte die *größere* von Unter- und Obergrenze, ein nach oben offenes Feld galt damit als Toleranzfeld — jetzt entscheidet die Obergrenze, sechs Felder betroffen, Registerprobe statt Einzelfall. **B38 gegenstandslos, gemessen**: Jeder Abstand kommt aus dem Raster, die 60/50/20 waren Summen geschachtelter Rasterschritte — falls je, wäre es die Entscheidung „welcher Schritt gilt für Abschnittsränder“, kein Befund. **B39 nicht reproduzierbar** (Messung 30.08. abends: Knopf endet bei 217, nicht 553; keine Trennlinie gefunden). B10: Der Zweispalter ist an der Messung gefallen (zwei Spalten à 598 = 1220 gegen 695 Dialogbreite — der eigene B8-Fix macht Spalten teuer, und ihn aufbrechen hieße einen geschlossenen Befund wieder öffnen). **Entschieden: Weg 3 in zwei Stufen** — die 16er-Gruppe „Haftung, Rückzug, Filament" ist kein Gruppentitel, sondern eine Aufzählung, und wird inhaltlich geteilt (eine Gruppe, ein Thema); danach wird bei Vorgabebreite gemessen, ob die Reiterleiste mit neun oder zehn Gruppen kippt — erst dann fällt der Entscheid über die vertikale Gruppenliste (die Slicer-Konvention, die bei D11 vertagt wurde), nicht auf Verdacht | M | **fertig** (15/53) — und die B10-Folge ist zu (`b04d765f`): Die Sammelgruppe „Haftung, Rückzug, Filament" ist in ihre drei Themen geteilt (größte Gruppe 9 statt 16 Felder; 40 von 56 Feldern lagen längst im Reiter ihres Pfads — dieselbe Doppelung wie beim Material, das die Spule schon kannte), der Test prüft Deckung statt Liste plus Obergrenze 9, und er fing prompt den Fehler des eigenen Massenumbau-Werkzeugs. **Die vertikale Gruppenliste ist gegenstandslos, gemessen am 30.08.2026**: Zehn Reiter passen bei Vorgabebreite — der Dreifachtitel war so breit wie die drei kurzen zusammen; Robert braucht keine Vorlage |
| G9 | **B12 ist zu** (`26e74652`): Die Einheit steht am Wert („Breite · 40,00 mm“) statt in der Beschriftung und wandert bei Zoll mit, was die Klammer nie tat; drei Nachbartests auf den neuen Ort umgestellt statt gelöscht. **B13 halb**: „fx“ und der Parameterknopf erklären sich in Kundensprache („Statt einer festen Zahl rechnen lassen — zum Beispiel die halbe Breite“), auch an Statuszeile und Bildschirmleser; die 60-Punkte-Lücke bleibt dokumentierte Absicht (Wert-Regel). Die Rahmen-Hälfte ist gemessen 72s: Die frische Zebrafarben-Ruhekante steht auf 1,13 gegen die Dialogfläche (Linienfarbe käme auf 2,30, WCAG-Nichttext will 3,0) — Entscheidung bei 72 mit B37. **B14 war durch `5f9fdcc6` miterledigt** — dieselbe unsichtbare QToolButton-Kante, von 15 am gebauten Fenster nachgemessen (98 Randpixel in der Linienfarbe, der Knopf steht als Kasten); ein Selektor, drei Befunde (B13/B37/B14). Dazu ein wertvoller Nicht-Bau: 36 Knöpfe ohne `accessibleDescription` sind kein Befund — Qt reicht den Tooltip als Description durch, gemessen am QAccessible-Interface statt am Attribut; 36 redundante Änderungen unterblieben | M | **fertig** (15/72) |
| G10 | **Zu, bis auf die B26-Auslagerung.** B17 (`aeb74155`): Chat-Begrüßung statt leerem Kasten, Modellzeile zuletzt. B29 (`48afea88` + Messung): dreizehn gleichlautende Beschriftungen wurden eine arbeitende Zeile; von den vier „nackten“ Wartezeilen stand nur der Generierungsdialog wirklich ohne Anzeige — B18 (`9c6ae78c`) gibt ihm einen unbestimmten Balken für die Prüfung (eine Prüfung hat keinen ehrlich bezifferbaren Fortschritt) und stellt ihn beim Erzeugungslauf ausdrücklich zurück, statt einen bei fünfzig Prozent weiterlaufenden zu erben. **B26 ist als eigenes Paket ausgelagert** — vier Eingriffe plus G6-Anteil am einzigen Dialog, an dem Geld hängt; der verdient eine eigene Runde mit frischem Kopf | M | **fertig** (72); B26 eigenes Paket, dazu der Ruhekanten-Kontrast (1,13 gegen WCAG 3,0 — 15s Messung) als Entscheid in derselben Runde |
| G11 | **Ein Erklärsatz war einen Bildpunkt breit und 176 hoch.** Der Schichthinweis der Skizzenkarte stand *neben* dem Ebenenfeld und bekam „den Raum, der danach noch übrig ist" — gemessen einen Punkt, gezeichnet als senkrechte Punktsäule, und `setMinimumWidth(1)` ließ Qt die Höhe aus `heightForWidth(1)` rechnen: dieselben 176 Punkte hätte er auch in einer eigenen Zeile behalten. Jetzt 574 × 16, die Zeichenfläche wächst um 160 Punkte. `use_viewport` beschrieb genau diese Rechnung samt der Zahl seit je und versteckte den Satz deshalb dort — für die Karte hatte es niemand gezogen. Kursiv (B19) an **beiden** Stellen der Anwendung durch `level="caption"` ersetzt. Die Kapsel „Keine Auswahl" erscheint erst, wenn es etwas zu wählen gibt (dafür zusätzlich an `sketchChanged`). Nicht bestätigt und deshalb nicht angefasst: „derselbe Satz doppelt" — im gebauten Fenster steht keine Beschriftung zweimal. Zwei Tests, sechs Gegenproben, alle rot | S | **fertig** (`e2839acc`, 50) |
| G12 | Druckeinstellungen: eine Abschnittsform statt QGroupBox-2010 über rahmenlosen Aufklappern (B9) | S | **fertig** (`b3a419fa`, 15): „Das Wichtigste“ und „Was dieses Teil verlangt“ sind jetzt Aufklapper wie ihre Nachbarn — eine Form, eine Sprache; die B9-Begründung steht als Docstring an der Stelle |
| G14 | **Roberts Order (30.08.2026): die Statusleiste unten komplett prüfen und sauber, modern, innovativ gestalten.** Dreistufig: (1) Bestandsaufnahme — jedes Element, seine Herkunft und seine Zustände (Statusmeldungen/announce, Fortschritt, Lizenzstand, Verbrauch; was erscheint wann), mit Belegbildern; (2) Gestaltungsentwurf im Ton der G6-Notiz — Hierarchie und Bereiche, Anzeige mit Weg (klickbare Auskünfte führen dorthin, wo die Sache lebt: Verbrauch zu den Druckeinstellungen, Lizenz zur Freischaltung), Symbole als zweite Kodierung, Akzent-Haushalt beachten; Review vor dem Bau; (3) Bau mit vorher/nachher. B24 war die Vorarbeit. **Der Entwurf liegt vor und ist gebilligt**: Heute zuckt bei 23 von 28 gemessenen Rechnungen ein Balken, der nichts sagt (elf davon unter 0,2 s — die häufigsten Gesten überhaupt); und die Entwurfs-Selbstkorrektur (72) machte den Bau kleiner: **Die 10-s-Schätzung existiert längst** (`remaining_time` samt „gleich fertig"-Fassung — die erste Suche hatte auf drei Signalnamen gegrept, an denen die Schätzung nicht hängt; die Suche antwortete sauber auf die falsche Frage). Wirklich fehlen zwei Stufen: unter 200 ms erscheint heute sofort etwas, und die Bis-2-s-Stufe (BusyCursor plus Statuszeile, ohne Balken) gibt es nicht als eigenen Zustand. **Entschieden: Die 2-s-Schwelle wird wörtlich nach §2.8 gebaut** — auch wenn eine 2,9-s-Rechnung ihren Balken dann nur 0,9 s zeigt: Das Abbrechen-Fenster ab zwei Sekunden gehört dem Kunden, und ein Balken, der in eine laufende Wartesituation eintritt (der BusyCursor steht ja schon), ist kein Zucken aus dem Nichts. Null zusätzliche Höhe, alle Widgets stehen. Der Stufen-Bau ist zu (`2400bfae` — zwei Zeitgeber, BusyCursor, die 2-s-Schwelle wörtlich; drei Gegenproben fallen an der jeweils gemeinten Zusage). Mitgeheilt: **eine G6-Regression, die seit `04fc6968` auf main stand** — der Symbol-Lesbarkeits-Wächter prüfte das Verhalten der entfernten `_recolour`-Methode, ohne ihren Namen zu tragen (die brauchbare Geschwisterfrage ist nicht „wer ruft das", sondern „wer würde rot, wenn das Gegenteil gälte"); der Test war zudem nur zufällig grün gewesen, weil er ohne Thema zweimal Windows-Systemfarben maß — der dritte Betriebslage-Fund des Tages, nachgezogen in `tests.md`. Der Test misst jetzt „das Zeichen ist auf seiner Fläche lesbar" gegen `active_fill` | M | **72** — offen: der Anzeige-mit-Weg-Teil des Entwurfs (Verbrauch klickt zu den Druckeinstellungen, Lizenz zur Freischaltung) und die LoadingVeil-Uhrenfrage |
| G15 | **Roberts Order (30.08.2026): „ebenso fensterrahmen usw" — das Fensterchrom komplett.** Titelleiste und Rahmen von Hauptfenster und Dialogen: prüfen, ob die Dekoration zum dunklen Thema passt (Windows malt die Titelleiste ohne Zutun hell — `DWMWA_USE_IMMERSIVE_DARK_MODE` ist der erste Kandidat), Fenster-Symbol, Dialograhmen, und die Frage, ob eine eigene Titelleiste (wie moderne Slicer sie führen) den Preis wert ist — Verschieben, Andocken, Systemmenü und Mehrschirmbetrieb sind der Preis, und die Antwort braucht eine Messung, kein Gefühl. Dreistufig wie G14: Bestandsaufnahme mit Belegbildern beider Themen, Entwurf mit Review, dann Bau | M | **d3, nach P2 und dem G6-Wächter** |
| G13 | Kleinserie: Filamentkarten-Höhe, Befehlspaletten-Spalten, Statuszeilen-Verschmelzung, Startbildschirm-Resthöhe, Filamentdialog (Farbfeld winzig, „OK"), Verlauf ohne Symbole, Menü-Icon-Lücken, Handbuch-Ränder, helle Kanten, sprachabhängiger Symbol-Schwellwert (B21/B23/B24/B27/B28/B31/B33/B34/B35/B40) | M | **läuft**: B35 ist zu (`5a921d07` — die Ursache war die Platte, nicht die Kante: Körper/Fläche 2,05→3,36, dunkles Thema und Kante unangetastet, Unmöglichkeits-Rechnung im Code; Belegbilder beider Themen liegen vor und sind von der Freigabe angesehen — die Trennung steht, B35 ist endgültig zu). **Neu aus dem Bilder-Ansehen (3a): die Themen sind unterschiedlich plastisch** — im dunklen zeichnet die Schattierung die Innenwände deutlich, im hellen wirkt der Körper flächiger; das ist eine Beleuchtungsfrage (ambienter Anteil je Thema), nicht eine Farbfrage, und läuft als eigener kleiner Punkt bei 3a nach B21 — Messung zuerst, die frischen B35-Kontraste bleiben unbewegt. **Plastizität ist zu** (`b0a72e14` — die Vermutung „ambienter Anteil je Thema" trug nicht: Es gibt keinen, die Beleuchtung ist in beiden Themen dieselbe. Ursache ist Multiplikation — der Körper ist im hellen Thema 2,45-mal dunkler, also sind alle Helligkeitsunterschiede auf ihm 2,45-mal kleiner (0,0155 gegen 0,0380 zwischen zwei Außenwänden). Ambient und Glanz gemessen und verworfen (ambient macht flacher: 1,19 → 1,12); getragen hat das Frontlicht, 0,25 → 0,45 im hellen Thema, +39 % absoluter Wandunterschied, dunkles Thema bitgleich unverändert. In derselben Reihe der Schatten-Auftrag: 0,18 ergab 1,44 Kontrast auf heller und 1,05 auf dunkler Platte — auf Roberts Entscheid „wie im dunklen thema reicht" jetzt 0,03 im hellen, gemessen 1,06. Jedes themenabhängige Paar trägt jetzt drei Zusagen: Richtung der Werte, `set_theme` setzt sie, die Zeichenstelle liest den gemerkten Wert — eine Mutationsprobe hatte gezeigt, dass „was die Methode tut" nichts über „dass sie gerufen wird" sagt. **Folge für die Auslieferung: die Bildschirmfotos in `app/images/` sind veraltet, `/erzeugen` vor dem nächsten Paketbau**); Roberts Schatten-Entscheid dazu: Der Kontaktschatten bleibt — er ist Auskunft, nicht Schmuck (§18.6). **B21 ist zu** (`a381e717` — der Befund war größer als notiert: Bei zwölf Spulen im Regal schob die aufgeklappte Karte ihren Hinweis und **beide Knöpfe** aus dem Bild, also den einzigen Weg zu einer neuen Spule, und drückte den Verlauf auf drei Zeilen (102 von 262 gewollt). Zwei Ursachen: Die Karte war kein `RoomTaker` und nahm sich, was sie wollte (614 statt 255); und `fit_to_rows` rechnet mit *einer* Zeilenhöhe mal Zeilenzahl, was bei fetten Zwischenüberschriften zu wenig ist — 172 gebraucht, 156 gesetzt, die letzte Zeile fehlte auch bei freiem Platz ringsum. Der Test fand beim ersten Lauf einen dritten Fall, das Nachziehen einen vierten (der verlorene `MAX_ROWS`-Deckel). **Fünf von sechs Sonden maßen etwas anderes als den Befund** — drei die zugeklappte Karte, zwei mitten in der Animation; `processEvents` lässt keine Zeit vergehen, die fünfte Gestalt in `qt-pruefstand-misst-zu-frueh.md`. Belegbilder vorher/nachher liegen vor und gingen an Robert); **B23 ist zu** (`4ceb179c` — die Morgenzahlen waren zu freundlich: real 475 Punkte Spanne durch Qts Tabstopp-Raster; ein Zeilenzeichner setzt Kürzel rechtsbündig, Restspanne 13 Punkte aus der Zeichenbreite). **B24 ist zu** (`c7765da4` — senkrechte Trennlinie zwischen den Auskünften in Status- und Kopfzeile, der Mittelpunkt trennt weiter innerhalb einer; der Commit nahm ~18 Zeilen von 50s laufender G11-Arbeit mit — `commit -o` statt Blob, Zurechnung falsch, Stand heil, 50 informiert). **B31 ist zu** (`a6d197d4` — Symbole aus derselben Quelle wie Menü und Katalog, unbekannte Ops bekommen keines statt eines falschen; Nummern für alles, was genau einen Schritt vertritt, weil der Fehlerdialog „Operation: 4" sagt und die Zahl die Verbindung ist; die zwei Punkte Zeilenhöhe je Symbol stehen als bewusste Abwägung im Code); B26 wartet auf den frischen Kopf; B33 ist komplett zu (`249d4241` + `c1ccc90d`) — und die Nachmessung korrigierte die Entscheidungsgrundlage: Bearbeiten war mit 0 von 8 in sich konsistent, der Sprung liegt **zwischen** den Menüs (Qt reserviert die Spalte je Menü: 16 gegen 36 Bildpunkte Texteinzug). Die Entscheidung trug mit erweiterter Reichweite: je ein Zeichen mit echter Metapher auch für Ansicht und Hilfe (redo gespiegelt, manual, about), sonst wandert der Sprung nur; das Zahnrad für „Einstellungen" wurde gezeichnet und verworfen — im Strichstil wird es eine Sonne, und Deko ohne Metapher bleibt verboten. Der Dreifach-Testfund dazu ist der allgemeinste des Tages: **Die Suite fährt ohne Stylesheet** (apply_style steht nur in app.py) — wer Einrückung, Breite oder Farbe misst, stellt die Betriebslage selbst her); B28 ist zu (`3430c7d0` — die Spulenfarbe ist so groß wie ihre Listenzeile; die „OK"-Hälfte war gegenstandslos, der Knopf hieß längst „Übernehmen"); B27 ist zu (`473a5b16` — ausbalanciert statt gefüllt: Die Spalte sitzt mit 1:3-Bias über der Mitte, und die Bilder entschieden die Zahl gegen die bessere Klangzahl — „69 % klingt besser als 62 %, sieht aber schlechter aus"; die viermalige Tour-Zeile steht einmal über der Gruppe und bleibt je Kachel beim Bildschirmleser, der Handbuch-Knopf nennt seine Handlung, der Satz steht im Hinweis; ein Nachbartest zog an den neuen Ort). B34 und B40 sind zu (`5719d4c7` — der Handbuchtext läuft auf 80 Zeichen statt 96, mitwachsender Rand; 80 statt der typografischen 60–70, weil Code und Tabellen die enge Fassung nicht vertragen. Qt-Fund darüber hinaus: `setViewportMargins` zieht die Dokumentbreite nicht mit, der Text hätte waagerecht gerollt — wer eine Textspalte begrenzt, setzt beides. Die Verzeichnis-Kürzung war korrekt, es fehlte der Weg zum ganzen Namen — der Hinweis trägt ihn. B40 als Mechanismus dokumentiert, nicht als Befund: Ein fester Umschaltpunkt wäre in genau einer Sprache richtig). **Damit ist die G13-Kleinserie komplett zu** |

Roberts Order zur Erhebung (30.08.2026): „das ganze dokument soll
vollständig abgearbeitet werden" — alle 40 Befunde, auch die
kosmetischen. Die Verteilung bündelt nach Dateien statt nach Schwere:
G1/G2/G3/G7 sind alle `style.py` und gehen als Serie an eine Hand,
damit nicht drei Sitzungen dieselbe Datei bewegen.

- [ ] Die dreizehn G-Pakete abarbeiten — je Paket Belegbild vorher und
      nachher, Zahlen und Review vor dem Commit; G1 zuerst, G6 nur
      über die Konzeptnotiz.
