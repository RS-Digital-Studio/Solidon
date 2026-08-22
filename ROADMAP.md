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
| Leistungsziele §31 der Schichtanalyse | P3 — Wahrnehmung und Schichtanalyse | einen CI-Baulauf, der `_chain` für Windows, macOS und Linux baut — dass es mitreist, ist seit dem 22.08. entschieden (Bauplan §31). Danach bleibt `_plane_segments` mit 893 ms die größte Position, nicht mehr GEOS |
| CI-Bauläufe und Signierung | P8 — Erste Veröffentlichung | einen CI-Dienst, der die Läufe fährt; die Signierung ein Zertifikat. AppImage und Flatpak stehen seit dem 20.08. |
| Doku, Website, Lizenzhinweise | P8 — Erste Veröffentlichung | Postfach `support@`, DMARC und den AVV im CCP |
| Sichtbarkeit | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | keine Entwicklungsaufgabe — bleibt bewusst stehen |
| macOS ausliefern | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | Apple-Zertifikat und Notarisierung; der Paketierschritt steht |
| DMARC fehlt | Die Demo bis 30.10.2026 (12.08.2026) | einen TXT-Eintrag im CCP |
| VTK stirbt in der CI, und die Fenstertests laufen dort nicht mehr | Die Demo bis 30.10.2026 (12.08.2026) | Runner mit GL oder ein VTK, das ohne auskommt; bis dahin prüft die Fenster, wer einen Bildschirm hat |
| Ein Gewinde auf macOS kann als STL Löcher haben | Die Demo bis 30.10.2026 (12.08.2026) | eine OCCT-Version, die den helikalen Gang dort am Kern schließt |
| Auf einem fremden Rechner installieren | Die Demo bis 30.10.2026 (12.08.2026) | einen fremden Rechner — die Dateien liegen seit dem 20.08. |
| Den helikalen Gang überall schließen | Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen | eine andere **Bauart** — alle sieben Griffe an `MakePipeShell` sind gemessen und widerlegt (20.08.), und ein Rotationskörper schraubt nicht |
| Der eine übersprungene Test | Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen | VTKs Zustand über mehrere Fenster hinweg |
| P16.10 — die Regel in der Sammlung | P16 — Organische Modellierung | eine Entscheidung; sie kostet zwei Agenten-Suite-Läufe und Geld |
| Der Absturz in einer einzelnen Datei | Ein Umgebungsartefakt, das keines war (14.08.2026) | einen ruhigen Baum und mehr als dreißig Läufe — dreißig am 20.08. blieben sauber, aber `panels.py` ist seit dem Fund fünfmal geändert worden |
| Ein dritter Absturz in `test_operation_ui.py` | Ein Umgebungsartefakt, das keines war (14.08.2026) | einen Lauf unter Valgrind — das Bild sagt „doppelt freigegeben", wer, sagt nur ein Werkzeug |
| Die Suite gegen Sonnet 5 | Die Konzepte nachrecherchiert (19.08.2026) | zwei Läufe über den Schlüssel des Nutzers; bis dahin ist die Quote eine Annahme |
| Die Werkzeugzeile der Skizze verlangt 1007 Bildpunkte — **entschieden** | Alle Bilder neu aufgenommen — und drei Fehler waren keine Bildfehler (20.08.2026) | einen Überlaufknopf: die acht häufigsten Zwangsbedingungen bleiben Knöpfe, der Rest wandert darunter. Achtzehn in einer Zeile sind auf einem 1366er Laptop nicht bedienbar, und `test_interface_limits.py` erlaubt acht Werkzeuge — die Hausgrenze stand schon. Welche acht: an Fusion ablesen. Dazu der Test, der sein Thema selbst setzt |
| Ein Höhenbudget für den Startbildschirm — **entschieden, in Arbeit** | Die Oberflächendurchsicht, zweiter Teil (20.08.2026) | eine Entscheidung darüber, **was** kleiner wird. Am 22.08. neu gemessen, und die Aktenlage des Punkts stimmt nicht mehr: 340 px fehlen auf 1600x900 statt 156, die Ablagefläche gibt es als Widget nicht mehr, und es sind **zwei** Kachelbereiche — `more_area` (242 px) ist der größte Einzelposten |
| Der exakte Zweig überlebt keine Mesh-Operation | Die Bedienung von Beispielen bis Skizze (20.08.2026, dritte Runde) | eine Entscheidung, ob `drill_hole` einen exakten Zwilling bekommt — der Hinweis nennt den Schritt inzwischen beim Namen, der Ausweg bleibt zurücknehmen und neu setzen |
| Stegdicke und Kammertiefe sind nicht gemessen | Die Nutfeder, und zwei Fehler auf dem Weg dorthin (20.08.2026) | zwei Werte vom Messschieber an einer 2020er und einer 3030er Schiene; bis dahin stehen die gebräuchlichsten Katalogwerte da, und `note` nennt die Spanne |
| Objektnamen der Beispiele bleiben deutsch | Der Durchgang durch die offenen Punkte, und ein Review über ihn (20.08.2026) | einen Schritt 8 → 9 im Dateiformat samt Migration — ein `TranslatableText` in `params` reicht bis in `operation_hash`, und ein Cache-Schlüssel darf nicht von der Anzeigesprache abhängen |
| „Eingabe korrigieren" ist ein Satz und kein Knopf | Der Bedienweg von außen nachgefahren (21.08.2026) | eine Entscheidung, was ein Handler tun soll — bei einem Parameterfehler den Dialog erneut öffnen, bei „andere Anzahl an Objekten" die Auswahl ändern, und das ist kein Dialog |
| Ein angeklicktes Gewinde bietet nichts an | Der Bedienweg von außen nachgefahren (21.08.2026) | den Eintrag „diesen Schritt ändern“ am erzeugten Merkmal — Bauplan §21.2 hat es am 22.08. über die Provenienz entschieden und nicht über `applies_to`, gilt damit für jede Merkmalsart. Bis dahin bleibt `thread` benannte Ausnahme im Konsistenztest |
| Verrundung und Fase gehen auf einem Netz nicht | Neun heruntergeladene Modelle durch die ganze Kette (21.08.2026) | den B-Rep-Kern für Eingelesenes; steht so im Bauplan, und dieser Lauf ist der Beleg, wie oft man dagegenläuft — bei jedem der neun Modelle |
| Der Absturz beim Aufräumen — Stelle bekannt, Ursache nicht | Der Schnapper griff nie, und der Absturz hat jetzt einen Stapel (22.08.2026) | einen Lauf unter einem Werkzeug, das doppelte Freigaben sieht. Zwei Stapel liegen vor, beide an derselben Stelle (`session.py:110`), aber über **verschiedene** Aufrufer — der finished-Slot war also nicht die Ursache. Die Falle steht in `tools/qt_trace.py` |
| Der lokale Weg auf Intel- und AMD-Grafik | Der Bildweg zum ersten Mal wirklich gefahren (21.08.2026) | eine Entscheidung, ob Solidon einen zweiten lokalen Weg **nennt** (IPEX-LLM, ROCm, OpenVINO) oder ob „hier lohnt es nicht, nimm einen Schlüssel“ die ganze Antwort bleibt; gemessen 7,8 Token je Sekunde und 41 Minuten bis zum ersten Wort |
| Erzeugen und Ändern sind reine Verteilermenüs — **entschieden** | Aus der Analyse für Neulinge und Kunden | die Zeilenbudget-Regel: Passen die Zeilen aller Kategorien einer Gruppe ins Zwölf-Zeilen-Budget, stehen sie flach mit Trennstrichen; sonst bleiben die Untermenüs. `MENU_GROUPS` schaut heute auf die Zahl der **Kategorien** — die Hausgrenze ist aber eine **Zeilen**grenze. *Erzeugen* wird damit flach (der Quader kostet zwei Klicks statt drei), *Ändern* bleibt tief. Kein Tausch: Die Neun-Menü-Grenze bleibt unberührt |
| Zwei fehlgeschlagene Operationen stapeln zwei modale Fehlerfenster | Aus der Analyse für Neulinge und Kunden | eine Entscheidung, was der zweite Fehler tun soll — unterdrücken, anhängen oder zählen |
| Dreißig Rümpfe im Viewport laufen in keinem Test | Vierzig Prozent der Ansicht sieht das Tor nie (22.08.2026) | eine Entscheidung je Methode, und die Reihenfolge steht seit dem 22.08. fest: erst prüfen, ob sich die Aussage vor die Wache ziehen lässt, und nur wo das nicht geht, eine Attrappe |
| Die Antwort der Zuordnung steht nirgends | Das Fundament der Wahrnehmung (22.08.2026) | die zweite Hälfte von Bauplan §15.7 — was eine **Operation** erfragt, steht seit `311134a` im Stapel; was die **Zuordnung** entscheidet (§21.3, die 99 Fenster), passt in keinen Parameter und braucht ein Feld an der Operation samt Formatänderung. Entwurf und offene Frage liegen in `.claude/memory/merkmalsmehrdeutigkeit-entwurf.md` |
| Ein geänderter eigener Baustein wird beim Öffnen nicht gemeldet | Das Fundament der Wahrnehmung (22.08.2026) | eine zweite Quelle für `changed_since_library` — sie liest gepflegte Änderungsverläufe, und ein eigener Baustein hat keinen (§24.4, §24.5). Gefunden von solidon-17 beim Anschließen des Plattencaches |
| Ein Verrundungsradius ist nicht abzulesen | Das Fundament der Wahrnehmung (22.08.2026) | das Torusstück einer Verrundung als Merkmal samt Radius, und die Krümmungskarte aus §18.4 mit echten Zahlen statt einer Färbung. Setzt die Erkennung von Kugel und Torus voraus (§41) und ist deren eigentlicher Gewinn — bis dahin sagt die Karte, *dass* es rund ist, und nicht *wie* rund |
| Die Zuordnung kennt Kugel und Torus nicht | Das Fundament der Wahrnehmung (22.08.2026) | zwei Arten mehr in der Kostenmatrix von §21.2, dazu Namen in der Oberfläche. Eine Art, die erkannt aber nicht zugeordnet wird, ist ein halber Zustand — dieselbe Konsistenzfrage wie bei den Übersetzungskatalogen, und beim Schneiden des Auftrags zunächst übersehen |
| Kugel und Torus fehlen der Erkennung | Das Fundament der Wahrnehmung (22.08.2026) | eine eigene Abnahme — Kegel ist seit dem 22.08. drin (§21.1), Kugel und Torus stehen als Ausbaustufe in §41. Eine Verrundung hat damit weiter keinen Radius |
| Keine Testart deckt „zwischen zwei Modulen“ | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung, ob §35 eine Zeile dafür bekommt. Der Plattencache war vollständig gebaut, vollständig geprüft und in der Anwendung nicht angeschlossen; jeder Test darunter war grün. Der Fehler saß nicht in einem Modul, sondern zwischen zwei |
| Ein Test, der nur seine eigene Konsistenz misst, sieht keinen systematischen Versatz | Das Fundament der Wahrnehmung (22.08.2026) | eine Frage an jede vorhandene Prüfung: gegen einen Wert von außen oder nur gegen die eigene Wiederholbarkeit? Zwei Fälle an einem Tag — die Krümmungskarte war bei jeder Netzfeinheit **gleich** falsch (zwei Drittel des wahren Radius), `ring_diameter` machte zwei verschieden große Tori ununterscheidbar |
| Die Krümmungskarte misst das Netz und nicht den Körper | Das Fundament der Wahrnehmung (22.08.2026) | eine Division — Winkel je Kantenlänge statt Winkel. Heute hängt die Aussage der Karte an der Vernetzungsdichte: Je feiner eine Verrundung vernetzt ist, desto glatter sieht sie aus. Entschieden ist Krümmung als Wert, Radius in der Legende |
| An einer Säule mit verrundetem Fuß wird kein Zylinder erkannt | Das Fundament der Wahrnehmung (22.08.2026) | eine Trennung nach **Krümmung** statt nach Knick — eine Verrundung schließt tangential an, und `CURVATURE_LIMIT` trennt an Knicken. Gemessen: sieben Flächen, kein Zylinder, Säule und Kehle ein Fleck aus 2305 Dreiecken |
| Der Testkorpus hat keinen verrundeten Körper | Das Fundament der Wahrnehmung (22.08.2026) | eine Datei mit Kehle. Ein Regressionsnetz, das die Alltagsformen ausspart, meldet Erfolg über dem, was es nicht enthält (§34) |
| In `parts/` ist der Nichtanschluss ein Rückfall | Das Fundament der Wahrnehmung (22.08.2026) | einen Aufrufer für `travelling_parts()` oder die Feststellung, dass es sie nicht braucht — und die Testart „Anschluss" aus §35, denn derselbe Fehler ist in derselben Datei schon einmal gefunden und behoben worden |
| Das Prüfschloss serialisiert die Rechenzeit, nicht den Arbeitsbaum | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung über eigene Arbeitsbäume. Jeder Lauf liest die ungestageten Dateien aller Sitzungen — ein fremder Zwischenstand macht einen Lauf rot, und schlimmer: er kann ihn grün machen |
| Ein Test steht zwölf Minuten still, ohne zu rechnen | Das Fundament der Wahrnehmung (22.08.2026) | einen Python-Stapel aus dem stehenden Prozess, also `py-spy` — das steht nicht in `constraints.txt`, und ein Werkzeug ungefragt in die Umgebung zu holen entscheidet Robert. Vierte Absturzsignatur, und die einzige, die steht statt abzustürzen |
| Der Stop-Hook meldet Zeitstempel, nicht Urheber | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung, ob der Hook das Sitzungsbrett selbst befragt. Bei vier Sitzungen schlägt er regelmäßig für fremde Arbeit an; wer den Umweg nicht geht, prüft fremden Code oder hält seinen eigenen für ungeprüft |
| `test_mesh_backend` misst die Umgebung statt sein Thema — **entschieden** | Das Fundament der Wahrnehmung (22.08.2026) | die dritte Zusicherung fällt. Sie prüft die Länge des Temp-Ordners **dieser Maschine** und sagt nichts über den Kunden; die zwei davor prüfen den Programmtext und bleiben. Ein Test, der bei umgebogenem `TEMP` rot wird, kostet jede Sitzung Zeit und schützt niemanden |
| Kein Viewport wird jemals freigegeben | Das Fundament der Wahrnehmung (22.08.2026) | eine Entscheidung über die Reichweite — die eine Zeile in `viewport.py` ist behoben, aber `.connect(lambda … self …)` steht an 59 Stellen in `app/ui/`, und jede davon ist ein Ring, sobald der Sender ein Kind von `self` ist. Könnte die gemeinsame Wurzel der vier Absturzpunkte sein: gemessen 7 MB je Fenster, und die Suite baut siebenhundert |
| Zwei Fensterdateien enden mit Exit 127, und einzeln auch | Das Fundament der Wahrnehmung (22.08.2026) | eine Ursache — die Roadmap nennt als Signatur des bekannten Absturzes „dieselbe Datei einzeln gefahren ist grün“, und diese zwei sind es nicht. Nachgewiesen im eigenen Arbeitsbaum auf HEAD, vollständig grün und dann 127 |
| Ein Absturz **vor** der Schlusszeile | Das Fundament der Wahrnehmung (22.08.2026) | eine Ursache — `test_ui.py` starb einmal von vier Läufen bei 95 Prozent mit Exit 139 in `conftest.py:178` (`processEvents()` im Teardown). Die bekannte Signatur ist „N passed, dann Absturz“; dieser hier riss den Lauf ab, bevor es eine Zusammenfassung gab |

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
- [~] Leistungsziele §31 für die Schichtanalyse — **zwei von dreien offen**,
      gemessen in `tests/test_performance.py`. Die Orientierungssuche (16,5 s)
      liegt im Ziel; die Wandstärkenkarte steht bei 3,08 s im Hintergrund und
      damit knapp über den drei Sekunden aus §31 — der Assert dort greift erst
      bei acht, hält also nur die Regression auf, nicht das Ziel. Die
      Schichtanalyse steht bei 1,05 s auf 328 000 Dreiecken, wo §31 für 200 000
      dreihundert Millisekunden nennt. Die Zahlen und die vier Änderungen, die
      dorthin führten, stehen unter „Leistung (§31) — Stand nach der
      Durchsicht". Was übrig ist, ist der Polygonaufbau in GEOS und braucht
      einen kompilierten Kern, keine weitere Python-Idee — **dass dieser Kern
      mit ausgeliefert wird, ist seit dem 22.08.2026 entschieden** (Bauplan
      §31), und damit gelten die Zielwerte dort ausdrücklich *mit* ihm. Offen
      ist nicht mehr die Entscheidung, sondern der CI-Baulauf für drei
      Plattformen; danach ist `_plane_segments` mit 893 ms die größte Position
      und nicht mehr GEOS

      **Nachgemessen am 14.08.2026**, und eine der Zahlen oben ist überholt:
      die Wandstärkenkarte steht nicht mehr bei 3,08 s, sondern bei **4,30 s**
      — auch allein gefahren, ohne Leistungsdatei davor. Die Orientierungssuche
      liegt mit 14,8 s im Ziel, die Schichtanalyse bei 1,07 s.

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
- [~] CI-Bauläufe, Signierung Windows, AppImage/Flatpak — `.github/workflows/`
      baut Windows und Linux, erst nachdem die Suite auf allen drei Plattformen
      grün ist. Windows wird zu einer Setup-Datei (`packaging/solidon3d.iss`,
      gebaut von `tools/make_installer.py`, das die Werte aus
      `app/branding.py` liest), Linux zu einem tar.gz, weil der
      Artefakt-Upload sonst die Ausführungsrechte verliert; Anwendung und
      Installer werden signiert, der Schritt überspringt sich ohne Zertifikat.
      **Ungeprüft**, weil dieses Repository noch nicht auf einem CI-Dienst
      liegt. Der Grund, der hier stand — es gebe kein Anwendungssymbol —, gilt
      nicht mehr: `app/images/icon/solidon3d.svg` ist die Quelle,
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

      **Kein Netzzugang im Flatpak.** `--share=network` wäre die bequemste Zeile
      und die falsche: Ohne Netz gibt es kein Konto, keine Telemetrie und keine
      Frage danach, und genau das ist die Zusage aus §2.1. Was drin ist, hat je
      einen Grund — Wayland und X11 für die Oberfläche, `dri` für den Viewport
      (§18), `home` für die Modelle, `org.freedesktop.secrets` für den Schlüssel
      des Agenten (§26).

      Zwei Stolpersteine sind vorweggenommen, weil sie sonst als Fehlermeldung
      ohne Absender erschienen wären: `appimagetool` ist selbst ein AppImage und
      braucht FUSE 2, das Ubuntu seit 24.04 nicht mehr mitbringt —
      `APPIMAGE_EXTRACT_AND_RUN=1` packt es vorher aus. Und der Upload steht auf
      `if-no-files-found: warn`, sonst hielte ein gescheiterter Paketierschritt
      das tar.gz zurück, das längst fertig ist.

      **Geprüft ist, was von Windows aus prüfbar ist**, und das ist mehr als
      nichts: `tests/test_packaging.py` hält die drei Beschreibungen an
      `app/branding.py` (dieselbe Drift-Prüfung wie bei den Handbuchabbildungen),
      liest die `.desktop`-Schlüssel, prüft die Metainfo als XML, verbietet die
      Netzberechtigung und verlangt, dass die CI das Werkzeug auch aufruft. Der
      **Bau** selbst braucht Linux und die beiden externen Programme — er bleibt
      ungeprüft wie der übrige Workflow, und aus demselben Grund
- [x] Erstinbetriebnahme (§38) — Sprache, Drucker, Material, externe Programme;
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

      Offen: Postfach `support@solidon3d.de` samt SPF/DMARC und der
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
bleibt bewusst außen (§22.5), OpenSCAD bleibt Rückfallebene. Die
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
* **Kaufmodell auf der Website** (Entscheidung Robert, Preis delegiert):
  14 Tage kostenlos testen, dann Einmalkauf — **49 € zur Einführung, später
  79 €**, alle 1.x-Updates inklusive. Einordnung: Plasticity als nächster
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

**Weiterhin offen, weil es niemand von hier aus erledigen kann:** das
Postfach support@solidon3d.de anlegen; Anschrift ins Impressum; Zertifikat
gegen SmartScreen; CI nie gelaufen; Zahlungsanbieter und
Lizenzschlüssel-Mechanik für Testphase und Kauf; ein Betatest mit fremden
Nutzern — 2100 Tests sagen, dass der Code tut, was gemeint war, nicht, dass
ein Fremder ihn bedienen kann. Anzumerken: die Web-Domain ist
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

- [ ] **Erzeugen und Ändern sind reine Verteilermenüs.** `registry.py:79` legt
      vier Kategorien unter *Erzeugen* und sieben unter *Ändern*, jede als
      eigenes Untermenü. Wer einen Quader will, klickt dreimal, und
      „Grundformen" hat vier Zeilen, wo die Grenze bei zwölf liegt. Wartet auf
      eine Entscheidung, wie tief ein Menü sein darf: flach ziehen sprengt die
      Neun-Menü-Grenze aus `tests/test_interface_limits.py`, ist also ein Tausch
      und keine Verbesserung. Die Namensdopplung „Vorbereiten →
      Druckvorbereitung" aus demselben Befund ist weg — `prepare` heißt heute
      „Teilen und Anpassen".
- [ ] **Zwei fehlgeschlagene Operationen stapeln zwei modale Fehlerfenster.**
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
      **Notarisierung**. `xcrun notarytool` und `stapler` kommen im Auftrag
      nirgends vor, und ohne sie hält Gatekeeper eine geladene Anwendung auch
      dann an, wenn sie signiert ist.
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
- [ ] **Ein Gewinde auf macOS kann als STL Löcher haben** (20.08.2026). Der
      Körper ist dort in Ordnung — geschlossen, ein Stück, richtiges Volumen,
      und STEP wie jede weitere Operation tragen ihn. Nur seine Vernetzung
      ritzt an der Flanke: M6 mit einem Millimeter Steigung bleibt undicht,
      auch nachdem `_finely_meshed` die Feinheit dreimal halbiert hat. Unter
      Windows und Linux sind alle Größen dicht. Der Test verlangt die
      Netzdichte deshalb überall außer auf Darwin; wer den STL-Export dort
      ernst nimmt, braucht einen anderen Weg als eine feinere Deflection.
- [ ] **Auf einem fremden Rechner installieren** (ohne Python, ohne venv, ohne
      OpenSCAD/Ollama/ComfyUI). Der Punkt, der erfahrungsgemäß mehr findet als
      alle Tests.
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

- [ ] **`test_operation_ui.py` bricht weiter ab, etwa einmal in acht Läufen.**
      Mit A und B hat er nichts zu tun: Er tritt auch dann auf, wenn die
      Plattform steht, unter `offscreen` wie unter `xvfb`, und er trat auf dem
      unveränderten Ausgangsstand in derselben Häufigkeit auf (ein Abbruch in
      sechs Läufen dort, einer in acht hier).

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
Vorarbeit dazu liegt in `.claude/.state/konzept-durchsicht-2026-08-19/`.

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

- [ ] **Der Startbildschirm braucht ein Höhenbudget.** Drei Kachelspalten statt
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
- [ ] **Die Werkzeugzeile der Skizze verlangt mit Stylesheet 1007 Bildpunkte.**
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

- [ ] **Der exakte Zweig überlebt keine Mesh-Operation.** Wer einen exakten
      Quader anlegt und eine Bohrung setzt, hat danach ein Netz — die
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

- [ ] **Die Objektnamen der Beispielprojekte bleiben deutsch — und der teure
      Teil ist ein anderer als hier stand.** Nachgesehen am 21.08.: Die
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

- [ ] **„Eingabe korrigieren" ist ein Satz und kein Knopf.** `CORRECT_INPUT`
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
- [ ] **Ein angeklicktes Gewinde bietet nichts an.** `thread` entsteht
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
- [ ] **Verrundung und Fase auf einem Netz sagen sauber ab** — `NeedsSolidError`
      mit dem richtigen Satz. Kein Fehler; nur ist damit für ein
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

- [x] **Der lokale Agent auf einem Rechner ohne nutzbare Karte: gemessen 41
      Minuten, bis eine Antwort beginnt.** Ollama spricht die Intel-Arc nicht
      an und rechnet auf dem Prozessor — `size_vram: 0.0`, 7,8 Token je Sekunde
      beim Einlesen. Der Systemprompt dieser Anwendung ist rund 19 000 Token
      lang. Die Anwendung sagte dazu nichts; sie sagte „Das Modell ruft
      Werkzeuge auf. Es ist brauchbar." Das ist wahr und nutzlos.

      Die Werkzeugprobe misst jetzt mit — ein Zug, der ohnehin läuft, und die
      Zahlen stehen in Ollamas Antwort. Sie nennt das Tempo, die Folge daraus
      und den einzigen Vorschlag, der hier trägt: einen Schlüssel für ein
      gehostetes Modell. Ein kleineres Modell rettet das nicht, und das steht
      ausdrücklich dabei. Die Geschwindigkeit **schlägt** die Werkzeugfrage:
      Wo eine Antwort einundvierzig Minuten braucht, ist es unerheblich, ob das
      Modell Werkzeuge aufruft.

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

- [ ] **Der lokale Weg ist auf Intel- und AMD-Grafik nicht praktikabel, und
      wir nennen keinen Ausweg.** Ollama unterstützt CUDA und Metal; auf allem
      anderen rechnet es auf dem Prozessor. Für Intel gibt es IPEX-LLM, für
      AMD ROCm-Versionen, für beides OpenVINO — jedes davon ist eine eigene
      Installation mit eigenen Fallen, und keines wird von Ollama selbst
      angeboten. Wartet auf eine Entscheidung, ob Solidon einen zweiten
      lokalen Weg **nennt** (nicht einrichtet) oder ob die Auskunft „hier lohnt
      es nicht, nimm einen Schlüssel" die ganze Antwort bleibt.

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

- [ ] **Was fehlt, ist der Beweis, nicht die Vermutung.** Nicht reproduzierbar:
      derselbe Dateisatz in derselben Reihenfolge lief beim zweiten Mal
      durch, und zwölf Läufe der Einzeletappe mit Instrumentierung blieben
      sauber. Damit wäre jede Änderung an der Auswertung geraten — und die
      naheliegende (den Neustart um einen Durchlauf der Ereignisschlange
      verschieben) greift in `wait_for_idle` ein, das genau darauf baut, dass
      `_worker` beim Verlassen des Slots wieder besetzt ist. Ein Hänger dort
      wäre schlimmer als ein seltener Absturz. Der Weg bleibt ein Lauf unter
      einem Werkzeug, das doppelte Freigaben sieht; die Falle steht jetzt
      dafür bereit.

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

- [ ] **Welche der dreißig verdienen eine Attrappe?** Nicht alle: Eine Attrappe
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

- [ ] **Die Antwort der Zuordnung steht nirgends.** Bauplan §15.7 hat am
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
- [ ] **Ein geänderter eigener Baustein wird beim Öffnen nicht gemeldet.**
      §24.4 verspricht einen Hinweis, welche *benutzten* Bausteine sich seither
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

- [ ] **Ein Verrundungsradius ist nicht abzulesen.** Die Krümmungskarte aus
      §18.4 färbt, was rund ist, und sagt nicht, *wie* rund — der Radius einer
      Verrundung steht nirgends. Er steht im Torusstück, das sie erzeugt, und
      dafür muss der Torus ein Merkmal sein. Damit ist dieser Punkt der
      eigentliche Gewinn der Kugel-und-Torus-Erkennung (§41) und nicht ihr
      Nebenprodukt: Wer eine heruntergeladene Verrundung nachbauen oder
      angleichen will, braucht die Zahl und nicht die Farbe.
- [ ] **Die Zuordnung kennt Kugel und Torus nicht.** Die Kostenmatrix aus §21.2
      führt die Merkmalsarten einzeln; zwei neue Arten, die erkannt werden,
      aber in der Zuordnung fehlen, sind ein halber Zustand — sie tauchen im
      Baum auf und finden über eine Auswertung hinweg kein Gegenstück. Dazu
      gehören ihre Namen in der Oberfläche, in allen fünf Katalogen.

      Beim Schneiden des Auftrags für Kugel und Torus zunächst abgeschnitten
      (3d-druck-64), und das war die falsche Grenze: Dieselbe Konsistenzfrage
      wie bei den Übersetzungen, die bewusst dazugenommen wurden. Acht Arten,
      die überall gleich auftauchen, schlagen zehn, die auseinanderdriften.
- [ ] **Kugel und Torus fehlen der Erkennung.** Vier Arten waren es, fünf sind
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
      kritischen Pfad des Starts liegen". Heute schon: `app/ui/app.py:234` ruft
      `load_operations()` vor `build_application()`, also lädt trimesh, während
      der Startbildschirm „Operationen werden geladen …" zeigt und Qt noch
      nicht hochgefahren ist. Beides parallel zu fahren wäre eine Änderung an
      der Startreihenfolge und damit eine Entscheidung — sie steht in der
      Vorlage an Robert, nicht hier. Gemessen von 3d-druck-64.
- [ ] **Keine Testart deckt „zwischen zwei Modulen“.** Der Plattencache war
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

- [ ] **Die Krümmungskarte misst das Netz und nicht den Körper.**
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

- [ ] **An einer Säule mit verrundetem Fuß erkennt die Wahrnehmung keinen
      Zylinder.** Gemessen am 22.08.2026 an einem echten Kehlkörper (Säule Ø12
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

- [ ] **Der Testkorpus hat keinen verrundeten Körper.** Deshalb fiel der Punkt
      darüber bis zum 22.08.2026 niemandem auf — nicht weil die Erkennung
      besser war, sondern weil nie jemand mit einer Kehle danach gefragt hat.
      §34 nennt den Korpus das Regressionsnetz der Wahrnehmung; ein Netz, das
      genau die Alltagsformen ausspart, meldet Erfolg über dem, was es nicht
      enthält.

- [ ] **In `parts/` ist der Nichtanschluss ein Rückfall, kein Einzelfall.**
      `tests/test_parts_catalog.py` schließt mit einem Test, dessen Docstring
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

      **Dieselbe Ursache beim Lesen statt beim Laufen:** `git diff` vergleicht
      gegen den **Index**, und im geteilten Baum liegen dort die Zwischenstände
      der anderen Sitzungen — ein Katalog-Diff zeigte fünf fremde Zeilen, die
      längst committet waren. `git diff HEAD` ist die Frage, die man stellen
      will: *Was unterscheidet meinen Arbeitsbaum vom letzten Commit?*
      Gefunden von 3d-druck-33.

      **Und dieselbe Ursache in ihrer teuren Form.** Weil vier Sitzungen mit
      privaten Indizes committen, zieht niemand den **gemeinsamen** Index nach.
      Am 22.08.2026 stand dort ein Schnappschuss von vor den Commits des
      Abends: `git diff --cached HEAD` meldete 27 Dateien, 87 Einfügungen und
      **1684 Löschungen** — darunter drei ganze Testdateien mit 343, 310 und
      159 Zeilen und zwei Korpusdateien. Ein einziges `git commit -a` hätte
      daraus einen Commit gemacht, und der post-commit-Hook hätte ihn sofort
      gepusht. Aufgeräumt mit `git reset` (ohne `--hard`, Arbeitsbaum
      unangetastet); gefunden von 3d-druck-b8, und zwar weil eine Datei nach
      ihrem eigenen Commit noch als `MM` im Status stand.

- [ ] **Ein Test steht zwölf Minuten still, ohne zu rechnen.** Gemessen am
      22.08.2026 von 3d-druck-33: `tests/test_interface_limits.py` blieb bei
      Test 23 von 30 (`test_the_tool_strip_comes_back_with_a_body`) stehen —
      **0,00 CPU-Sekunden in acht Sekunden Messung** bei 508 MB
      Arbeitsspeicher. Der Prozess rechnete nicht, er stand. Dieselbe Datei lief
      bei einer anderen Sitzung in 9,6 s durch, und einzeln nachgefahren: 30
      passed in 10,77 s, Exit 0.

      **Das ist eine vierte Signatur neben den drei bekannten** — und die
      einzige, die *steht* statt abzustürzen. Die anderen drei enden mit
      `0xC0000409`, mit Exit 127 oder mit einer Zugriffsverletzung; diese endet
      gar nicht. Zum Nachsehen fehlt ein Python-Stapel aus einem laufenden
      Prozess, also `py-spy` — das steht nicht in `constraints.txt`, und ein
      Werkzeug ungefragt in die Umgebung zu holen ist eine Abweichung, die
      Robert entscheidet und keine Sitzung.

- [ ] **Der Stop-Hook meldet Zeitstempel, nicht Urheber.** Bei vier Sitzungen
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

- [ ] **`test_mesh_backend` misst die Umgebung statt sein Thema.**
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

- [ ] **Kein Viewport wird jemals freigegeben, und kein Fenster auch.** Gemessen
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
- [ ] **Zwei Fensterdateien enden mit Exit 127, und einzeln auch.**
      `tests/test_chat_ui.py` (40 passed) und `tests/test_first_run.py`
      (45 passed) laufen vollständig grün durch und beenden sich dann mit 127.
      Nachgewiesen von solidon-17 im eigenen Arbeitsbaum auf HEAD — also weder
      ihre noch meine Arbeit. **Das ist eine andere Signatur als der bekannte
      Absturz beim Aufräumen**, dessen Kennzeichen in dieser Datei lautet:
      „Dieselbe Datei einzeln gefahren ist grün." Diese zwei sind einzeln nicht
      grün, sie reproduzieren jedes Mal. Entweder hat sich die wandernde dritte
      Stelle festgesetzt, oder es ist eine dritte Ursache.

      **Und eine Warnung an den nächsten, der es nachfährt:** Ich hatte beide
      einzeln gefahren und „grün, Exit 0" gemeldet — der Exit-Code kam aus einer
      Pipeline (`pytest … | tail -8; echo $?`) und war der von `tail`. Die
      Zahl der bestandenen Tests war echt, der Exit-Code nicht. Wer diesen Punkt
      prüft, schreibt die Ausgabe in eine Datei und liest sie danach.

- [ ] **Ein Absturz vor der Schlusszeile ist eine dritte Signatur.**
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
