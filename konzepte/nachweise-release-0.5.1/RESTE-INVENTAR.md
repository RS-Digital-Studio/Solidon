# Reste-Inventar der Durchsicht v0.5.1

Stand: 27.09.2026 gegen 22:10, main = origin = `1163c30d7`. Nur lesend erstellt.

Quellen: alle `reports/*-schluss.md` und `reports/*-antwort.md`, die Tabelle
„Stand je Paket“ in `UEBERGABE.md` (Zeilen 140–172, dazu „Übernahme“ und
„Entscheidungen“), `KOORDINATION.md`, `reports/register.md` und
`reports/ast-flake.md` (beide ohne Schlussbericht) sowie in den fortlaufenden
Berichten die Abschnitte „Registersätze“, „Für Nachbarn“ und „Übertrag aus dem
Register“. Abgeglichen gegen das Register in `ROADMAP.md`, gegen
`ROADMAP-ARCHIV.md`, gegen `git log v0.5.0..main` (311 Commits) und, wo nötig,
gegen den Code am HEAD.

Nicht als Rest gezählt: die Schritte des Release-Ablaufs selbst (Versionssprung,
Tag, CI-Bau, Signierung, Download-Kasten, Upload), die in `UEBERGABE.md` oben
stehen, und reine Zusammenführungshinweise der Pakete, die mit der Übernahme
erledigt waren.

Kategorien: `code` im Repository behebbar ohne Robert · `entscheidung` braucht
Robert · `extern` Hardware, Konto, Geld oder Probedruck · `release` Abnahme am
echten Fenster, auf ruhiger Maschine oder am echten CI-Lauf · `fremd` gehört der
Sitzung „Gesamtprüfung und RM-281“ bzw. „Handbuchumbau fortsetzen“ · `erledigt`
durch Commit belegt · `hardware` Folge der falsch rechnenden CPU (RM-272).

**Laufende Arbeit an registrierten Punkten (Stand 22:02):** Unter
`F:\3D Druck.review-051\` sind neue Worktrees auf `1163c30d7` angelegt —
`wt-bohren` (Zweig `rm-274-bohren`), `wt-schraube` (`rm-276-schraube`),
`wt-kanten` (`rm-279-kanten`, `tests/test_mesh_edges.py` geändert) und `wt-tor`.
Keiner der Zweige hat einen Commit über main.

---

## 1. Nicht registriert und nicht erledigt

24 Reste: `code` 18 (davon 3 ausdrücklich „zur Kenntnis“), `entscheidung` 1,
`extern` 1, `release` 3, `fremd` 1.

### Kategorie `code`

**1.1 Nach *Kanten verfeinern* kommen gleich große Verrundungen unter neuen Namen zurück** — falsches Ergebnis
- Quelle: `reports/reparatur.md:643–649` (Für Nachbarn erkennung), `reports/reparatur.md:551` (Sollliste 10, „Einschränkung“).
- Messzahl: Ring des Siebhalters (`Siebhalter+X1C.3mf`) 3 von 48 Verrundungen (`fillet_1`–`fillet_3` → `fillet_4`–`fillet_6`, bitgleiche Maße), Fettpressenhalter (`Elegoo_erster_Druck.3mf`) 2 von 22 (`fillet_2`/`fillet_3` → `fillet_7`/`fillet_8`). Ein Verweis auf den alten Namen (Passung, späterer Schritt) verwaist.
- Fundstelle: Zuordnung nach dem Verfeinern; die Herkunft je Dreieck trägt `mesh_ops._split_conforming` als `face_id`, gelesen von `features.refined_twin`.
- Weg laut Bericht: gleich große Verrundungen um dieselbe Mitte über die Herkunft je Dreieck (`face_id`) zuordnen.
- Stand: vom Paket erkennung nicht aufgegriffen (in `reports/erkennung.md` kein Wort dazu), nicht im Register. ERKENNUNG-02 (`6217c57f9`) behob nur das Wiederöffnen, `e805f511f` trägt die Herkunft durch Boolesche für die Zählregeln. Am HEAD nicht nachgestellt. Sonde `sonden\reparatur\verfeinern_kundenweg.py`, Rohdaten `verfeinern2.txt`.

**1.2 Zusage „Taschen und Abflachungen“ der Stellen-Erkennung nur an Prüfkörpern belegt** — Verständnis
- Quelle: `reports/erkennung-antwort.md:29–30`.
- Betroffen: `changelog/de.md`, 0.5.1, Erkennen, dritter Punkt („findet *Merkmale an einer Stelle erkennen* Flächen, Taschen und Abflachungen …“).
- Weg: an Modellen aus `F:\3D Dateien` nachweisen, sonst den Satz einschränken.

**1.3 Hinweis `settings.uncalibrated_material` an jedem Teil einer frischen Installation** — Bedienung
- Quelle: `reports/druck.md:273` (Für Nachbarn), `reports/register.md:101–103` (bewusst „zur Kenntnis ohne Arbeit“).
- Messzahl: genau ein Hinweis an jedem Teil; wirksam nur bei Teilen mit Passungen (`auto:`-Toleranzen).
- Fundstelle: `slice/advise.warnings_for` über `findings.print_findings`.
- Weg laut Bericht: den Hinweis nur zeigen, wenn die Szene Passungen trägt (`Scene.fits`). Entschärft ist nur das Urteil: Hinweise zählen seit `3b57b3644` nicht gegen „Druckbereit“.
- Hinweis: `advise.py` ist zugleich Arbeitsgebiet der Sitzung „Gesamtprüfung und RM-281“.

**1.4 Fadenkreuz der Stellenwahl in den Renderer verlegen** — Bedienung, Empfehlung
- Quelle: `reports/fenster.md:955–958` (Für Nachbarn massbild), `reports/register.md:104` („Vorschlag“).
- Fundstelle: `app/ui/viewport.py`, heute vier deckende Arme als Widgets über der Ansicht (FENSTER-17, `336c7fdc8`).
- Weg laut Bericht: Arme in den Renderer, Fokus und Namen weiter über ein kleines Widget. Kein Fehler.

**1.5 `carpet-corner-clip.step` braucht bis „geöffnet“ 201 s** — Leistung
- Quelle: `reports/massbild.md:522–523` (Für Nachbarn reparatur/ingest), `reports/register.md:115–118` (offene Frage 2: „nachmessen und ggf. als RM-273 anlegen?“; RM-273 ist inzwischen anders vergeben).
- Messzahl: 201 s unter Last, nebenbei beobachtet, nicht gegen HEAD gemessen.
- Vermutung laut register: dasselbe wie REST-BOHRUNG-01 (exaktes Volumen im UV-Rückfall), das `b0d344e5c` an gs-100 von 24,4 auf 1,5 s gebracht hat.
- Weg: am HEAD nachmessen; bleibt es langsam, eingrenzen und als Punkt führen.

**1.6 Größenänderung einer großen Bohrung noch rund 26 s** — Leistung
- Quelle: `reports/werkzeuge.md:290–294` (Für Nachbarn erkennung/bohrung).
- Messzahl: nach WERKZEUGE-03 (`68cd2ef6f`, 61–83 → 26–28 s) rund 26 s je Größenänderung (Profil `sonden/werkzeuge/floor2.prof`).
- Fundstelle: verteilt über `_large_facet_faces_read`, `relations._blended_cavity_faces` (`cavity_surface_indices`) und `detect`.
- Einordnung laut Bericht: gehört zur Frage aus RM-132/RM-193. Seither beschleunigt, aber nicht nachgemessen: `84aa9a5aa` (örtliche Nachmessung), `e1b897ca2` (Merker über die Körpergrenze).

**1.7 Eigenkreuzungs- und Überschneidungssuche kostet 7,5 bis 8,3 s** — Leistung
- Quelle: `reports/reparatur.md:686–691` (Für Nachbarn bohrung), `reports/rest-teilen.md:405–409` (Für Nachbarn Reparatur).
- Messzahl: vollständige Suche am Besenhalter 7,5 s unter Last (`intersections._candidates` 5,8 von 6,4 s, darin `_separated` 2,9 s); große Hälfte des Laptop-Ständers 8,3 s einmal je Modell und Prozess beim ersten Booleschen Schritt (`intersections.crossing_face_pairs`, `_candidates` 3,1 s Eigenzeit).
- Stand: Das Archiv (RM-266) nennt die 8,3 s als Rest am Ständer und verweist auf die Eigenkreuzung von RM-253; einen Punkt zur Laufzeit der Suche gibt es nicht.

**1.8 Schichtanalyse ineinandersteckender Teile schneidet über `polygonize` und `unary_union`** — Leistung, „für später“
- Quelle: `reports/rest-teilen.md:410–413`.
- Messzahl: 60 % der Schnitte, je Schicht rund 5 ms, `union_all` gut die Hälfte davon; der Weg hält den GIL und skaliert nicht auf Fäden.

**1.9 17 offene Registerpunkte verweisen auf Dateien im Review-Ordner, der nach dem Release aufgeräumt werden soll** — intern, Unterlagen (beim Abgleich aufgefallen)
- Quelle: `UEBERGABE.md:73–74` („Aufräumen erst nach dem Release: … dieser Ordner“) gegen `ROADMAP.md` (21 Pfade `F:\3D Druck.review-051\…` in RM-187, -212, -213, -232, -251, -252, -253, -259, -262, -272 bis -276, -278 bis -280).
- Tragend sind vor allem der Drehweg `sonden\rest-muendung\prepare_ops_mit_drehen_heute.patch` (RM-262), der exakte Prototyp `sonden\rest-muendung\m19_exakt_band.py` (RM-259), die Sonden von RM-274/-275/-276/-279 und das Profil von RM-273.
- Weg: vor dem Aufräumen die tragenden Dateien ins Repository holen (etwa unter `konzepte/` oder `.claude/.state/`) oder die Verweise anpassen.

**1.10 `analysis._plane_segments` reicht einen möglicherweise nur lesbaren Puffer an den übersetzten Kern** — intern, Härtung
- Quelle: `reports/reparatur.md:675–679` (Für Nachbarn druck).
- Fundstelle: `app/core/slice/analysis.py:1010–1015`, `np.ascontiguousarray(...)` → `_chain.plane_segments`.
- Stand: Die Quelle von REPARATUR-10 ist behoben (`300ab4da3`); die empfohlene Kopie bei nicht schreibbarem Puffer, die jeden künftigen Erzeuger finge, fehlt am HEAD.

**1.11 `threemf._reading_trees` taut mit `gc.unfreeze()` den ganzen Prozess auf; `leash.undisturbed` verträgt keine überlappende Nutzung aus zwei Fäden** — intern
- Quelle: `reports/ast-flake.md:47–53` („Codebefund ohne Bezug zur Ursache“).
- Fundstelle: `app/core/ingest/threemf.py:2224`, `app/ui/leash.py:576`.
- Stand: heute folgenlos, weil sonst niemand einfriert; zwei gleichzeitige 3MF-Lesevorgänge in zwei Arbeitern tauten einander auf. Logik, keine Speichersicherheit.

**1.12 Veralteter Kommentar in `app/ui/loading.py`** — intern
- Quelle: `reports/erkennung.md:1046–1052` (Für Nachbarn fenster).
- Fundstelle: `ProgressTiming.remaining`, Zeilen 266–269 („die bestätigte Vollerkennung, die nur ihre Spanne nennt — schriebe sonst neben „geschätzt 2 bis 13 min“ …“).
- Weg laut Bericht: den bleibenden Grund nennen (Pausen ohne Anteil), nicht die Spanne. Am HEAD unverändert.

**1.13 Kommentar an `features.WHOLE_BODY_ANSWERS` nennt 75 statt gut 90 Megabyte** — intern
- Quelle: `reports/rest-kern-schluss.md:62–63`, `reports/rest-kern.md:379–385`, `UEBERGABE.md:167`; auch im Archiv bei RM-260 (`ROADMAP-ARCHIV.md:32572–32574`) vermerkt.
- Messzahl: gemerkter Oberflächenindex am Gartenschlauchhalter 15,7 MB Felder und 63 353 Baumknoten mehr (72,2 → gut 90 MB), bis zu acht gemerkte Indizes.
- Fundstelle: `app/core/perceive/features.py:6809`, am HEAD unverändert.
- Achtung: `features.py` trägt im Hauptbaum ungestagete Doctor-Docstrings („nicht anfassen“).

**1.14 Lehre zu `np.fmin`/`np.fmax` und `np.unique(axis=0)` steht nirgends** — intern, Unterlagen
- Quelle: `reports/werkzeuge.md:295–300` („Für die Erinnerungen“), `reports/register.md:105–106` (als Erinnerung vorgesehen).
- Inhalt: `np.fmin`/`np.fmax` verwerfen ein NaN (in einem konservativen Test ein stilles Verwerfen); `np.unique(axis=0)` kostet an kleinen Feldern ein Vielfaches einer `lexsort` mit Laufgrenzen.
- Stand: `.claude/memory/*.md` und die Regeln ohne Treffer.

**1.15 Alter Scratchpad einer früheren Sitzung hält 182 MB** — intern, Aufräumen außerhalb des Repositorys
- Quelle: `reports/druck-antwort.md:36–37`.
- Ort: `%USERPROFILE%\AppData\Local\Temp\claude\F--3D-Druck\96f0dd6a-d08f-4976-bf3d-0e7c0346de71\scratchpad\` mit `head/` (77 MB), `v050/` (45 MB), `wtsnap/` (60 MB), Eigentümer unklar; am 27.09. vorhanden.

Zur Kenntnis — vom Bericht ausdrücklich ohne Arbeitsauftrag, im Register bewusst nicht geführt:

**1.16 Netzfehlerkarte rechnet an großen Körpern bis doppelt so lange, dafür vollständig** — Leistung
- Quelle: `reports/reparatur-schluss.md:47–48`, `reports/reparatur.md:826–832`, `reports/register.md:101–102`.
- Messzahl: 6 bis 16,5 s gegen 5 bis 11 s unter Last (349 000 bis 794 000 Dreiecke); §31 nennt für diese Karte keine Zahl.

**1.17 *Dreiecke verringern und erneut versuchen* misst die Abweichung nicht** — Verständnis
- Quelle: `reports/rest-verlauf.md:370–374`.
- Messzahl: Methode *Schnell*, Meldung „Schnell verringert — die Abweichung wurde nicht gemessen.“; Spielwürfel −0,6 % Volumen. Der gemessene Weg kostete 4 bis 24 s je Probe.

**1.18 Einzelne Auswahlen `….faces[…]`/`….vertices[…]` außerhalb von `perceive`** — intern
- Quelle: `reports/rest-erkennung2.md:609–615`, `reports/register.md:103–104`.
- Fundstellen: `geom/prepare_ops.py` (5552, 8566–8572, 9358–9359, 9969), `geom/intersections.py` (370, 751–752), `geom/seal.py` (259), `geom/section.py` (219), `geom/edges.py` (2156, 3032), `ingest/threemf.py` (1061, 1063) — keine in einer Schleife über Flecken, die Regel verlangt es nur dort.

### Kategorie `entscheidung`

**1.19 Schiffssatz im Changelog: Anteil oder Sekunden** — Verständnis
- Quelle: `reports/reparatur-schluss.md:46`, `reports/reparatur.md:816–821`, `KOORDINATION.md:117–118`, `reports/register.md:112–114` (bewusst nicht ins Register).
- Betroffen: `changelog/de.md`, 0.5.1, Einlesen und Reparieren, letzter Punkt („… braucht rund 30 Prozent weniger Zeit“).
- Messzahl: 26–37 % schneller, A/B im selben Prozess unter Last.
- Optionen laut Bericht: Anteil bleibt; oder auf ruhiger Maschine nachmessen (`sonden\reparatur\ab_normalise.py`, v0.5.0 gegen HEAD) und Sekunden einsetzen. Die Erinnerung „Druckzeit als Anteil“ spricht für den Anteil.

### Kategorie `extern`

**1.20 Changelog-Satz „damit die Düse unterwegs weniger ausläuft“ ist ungemessen** — Verständnis
- Quelle: `reports/texte.md:364–365` (Für Nachbarn druck), `reports/texte-schluss.md:11` (Punkt #42).
- Betroffen: `changelog/de.md`, 0.5.1, Drucken und Übergabe, fünfter Punkt („… mit 500 statt 150 mm/s, damit die Düse unterwegs weniger ausläuft“).
- Weg laut Bericht: mit dem Probedruck aus RM-247 belegen, sonst den Nebensatz streichen. RM-247 nennt den Probedruck, nicht diesen Satz.

### Kategorie `release`

**1.21 Erzeugnisse neu erzeugen; bis dahin bleiben Tests rot** — intern
- Quelle: `reports/texte-schluss.md:19`, `reports/erkennung-schluss.md:23–25`, `reports/fenster-schluss.md:39–42`, `reports/ki.md:661–667`, `reports/ki-antwort.md:17`, `reports/rest-klick-schluss.md:28`, `reports/rest-auswahl-schluss.md:21–22`, `reports/rest-schraube-schluss.md:21–22`, `reports/register.md:107–108`.
- Messzahl: rot bis `/erzeugen` — `test_manual.py` 18 Fälle, `test_wording::test_every_manual_paragraph_reaches_the_generated_page` 6 Fälle, 30 `rendered`-Fälle (darunter `test_the_checked_in_manual_carries_the_current_model_measurements`).
- Inhalt: Handbuch, Website-Handbuchseiten, Figuren, `version.json`; dazu die von KI-09 berichtigten Website-Seiten (12 Seiten, nicht hochgeladen; Upload nur mit Roberts Freigabe).
- Stand: steht im Release-Ablauf von `UEBERGABE.md` (Schritt 4), kein Registerpunkt.

**1.22 Changelog „in einem Drittel der Zeit“ ließe sich nach einer v0.5.0-Messung schärfen** — Empfehlung
- Quelle: `reports/rest-klick.md:477–485`.
- Messzahl: heute 74–79 ms Bohrung zu Bohrung gegen 673–718 ms in der älteren massbild-Messung.
- Weg laut Bericht: v0.5.0 mit derselben Messgrenze (Ende des ersten Bildes mit Maßen) messen; trägt es, „in einem Achtel der Zeit“.

**1.23 Berichtsseite fortschreiben und Abschlussbericht an Robert** — intern
- Quelle: `UEBERGABE.md:73–76` und `:241`.
- Inhalt: `bericht/durchsicht.json` → `durchsicht-v0.5.1.html`, Artifact `HDL6bEr2Ewso59WE5AVzLy`; danach `wt-merge`, der Review-Ordner und die Erinnerung `durchsicht-051-uebergabe` (vorher 1.9 erledigen).

### Kategorie `fremd`

**1.24 Druckdialog während der Erkennung schneidet selbst** — Leistung
- Quelle: `reports/fenster.md:946–952` (Für Nachbarn druck).
- Inhalt: Seit das Bild vor der Erkennung steht, startet die Schichtanalyse des Prüfberichts erst mit dem Ergebnis. Öffnet der Kunde den Druckdialog vorher, findet `_AdviceWorker` keine gemerkte Analyse und schneidet selbst — kein Fehler, nur kein Gewinn aus DRUCK-14 in diesem Zeitfenster.
- Gehört zum Druckdialog und damit zur Sitzung „Gesamtprüfung und RM-281“.

---

## 2. Registriert und offen

41 Punkte: `code` 13, `entscheidung` 9, `extern` 3, `release` 11, `fremd` 5.

| RM | Titel | Kategorie | Was an diesem Punkt noch offen ist | Quelle |
|---|---|---|---|---|
| RM-276 | Gedruckte Schraube liegt ohne Spiel am Sitz | code | An Ort und Stelle gedruckt verschweißt der Kopf; Weg (a) Spiel aus dem Materialprofil an der Kopfauflage mit `LIBRARY_VERSION` und Bereichsnachweis, laut Register nicht vor dem Tag v0.5.1 — Zweig `rm-276-schraube` angelegt, ohne Änderung. | rest-schraube-schluss.md:14 |
| RM-277 | Schräg gesetzte Magnettasche verliert die Lippe auf der hohen Seite | code | Kein Befund, obwohl die Lippe unter 10° auf 31 %, unter 20° auf 41 % des Umfangs fehlt; Hinweis mit *Eingabe korrigieren* und neuer Satz in sechs Sprachen. | rest-schraube-schluss.md:17 |
| RM-253 | Laptop-Ständer: Kippen und Verdoppeln einer Bohrung tragen falsch ab | code | Die Geometrie: Teil 10 kreuzt sich 1 121-mal selbst, gekippt liegen 32,6 mm³ jenseits der alten Kappe; dazu 13 von 28 Bohrungen „steht Material“ und das nicht wiedererkannte Langloch. | bohrung-schluss.md:31; massbild.md:517 |
| RM-259 | Mündungsrundung in gekrümmter Fläche reist nicht mit der Senkbohrung | code | Gekrümmt offen: Netz-Erkennung der Senkung hinter einer Rollkugelrundung, Fortsetzung zusammengesetzter Flächen, exakter Prototyp samt Bandkennung; Abnahme gegen −2,97 / +0,29 / −4,56 mm³ an gs-100. | rest-muendung-schluss.md:9 |
| RM-274 | *Bohrung setzen* mit freier Richtung versetzt unberührte Ecken | code | 17 572 von 196 326 Ecken am Gartenschlauchhalter; Werkzeug in die Welt legen, `_restore_drill_end_planes` mitziehen — Zweig `rm-274-bohren` angelegt, ohne Commit. | rest-merker-schluss.md:51 |
| RM-275 | Musterbezug auf rundem Träger kippt zwischen gleichen Zellen | code | Wahl des Bezugs in `perceive/patterns.py` von der Darstellung lösen, am Korpus gegen die Schrittfolge messen. | rest-merker-schluss.md:53 |
| RM-226 | Netz und exakter Kern nennen dieselbe Fläche verschieden | code | Aus der Durchsicht: Tiefe eines gefasten Langlochs je Kern verschieden (2,01 gegen 3,20 mm) und zweiter Satz einer Langloch-Kopie über die Kante (`feature_lost` gegen `no_longer_through`). | rest-erkennung2-schluss.md:55 |
| RM-262 | Die Erkennung liest eine gekippte Haltelippe nicht | code | *Merkmal drehen* an der Magnettasche bleibt abgesagt, bis beide Erkennungen Tasche, Lippe und Schacht als Kette lesen; dazu die winzige Lippe nach Ø 8,0 nur am exakten Kern. | rest-muendung-schluss.md:10; rest-lippe-schluss.md:40 |
| RM-217 | Zuordnungsfrage zeigt das alte Merkmal nicht im Bild | code | `question_context` trägt das alte Merkmal nicht zur Ansicht (Kernvorschlag: `FeatureQuestionContext` mit Art, Mitte, Achse, Hüllquader). | erkennung-schluss.md:35 |
| RM-278 | Zug in der Öffnung einer Senkbohrung verschiebt den ganzen Körper | code | Bedienentwurf über `bedienlogik` (Langloch samt Senkung, Versetzen oder nichts), dann Kern und Ansicht. | rest-auswahl-schluss.md:17 |
| RM-273 | Das Übernehmen rechnet die Operation noch einmal | code | 16–17,5 s statt unter 10 s am Gartenschlauchhalter; Vorschauergebnis übernehmen oder Nachmessung auslassen. Die örtliche Wiedererkennung (Bauplan §21.1) bleibt Entscheidung Robert, Empfehlung: nicht. | rest-merker-schluss.md:40 |
| RM-209 | Rundform-Einpassung an Gittermodellen | code | 42 000 Löserläufe an 167 000 Stücken (Meshy-Murmelbrett 342,8 s); zwei Hautregeln gemessen und verworfen. | erkennung-antwort.md:10 |
| RM-187 | Dieselbe Geometrie auf jeder Plattform | code | Aus der Durchsicht: Teilungsweg über BLAS (REST-TEILEN-06), Einsetzen eines Bausteins, Drehwege von *Merkmal drehen*; dazu die Fingerabdrücke auf den drei Runnern. | rest-teilen-schluss.md:12; UEBERGABE.md:160 |
| RM-272 | Die Entwicklungsmaschine rechnet zeitweise falsch | entscheidung | CPU-Tausch über Intels Garantie; bis dahin Intel Default Settings, MemTest86, Release-Pakete in der CI oder doppelt bauen. Release-Tor und Erzeuger mit Affinität ohne die Kerne 8–11 (`FFFFF0FF`). | UEBERGABE.md:156; ast-flake.md:225 |
| RM-279 | „Alle waagerechten Kanten“ nimmt die Ränder einer Querbohrung mit | entscheidung | Alte Projekte über Migration wie gespeichert oder neues Verhalten ab einer Version mit Meldung; dann `choose` über `edge_lie_of` — Zweig `rm-279-kanten` angelegt, Test geändert, ohne Commit. | rest-kunde-schluss.md:20 |
| RM-212 | Vorschau großer Teile hält den Hauptthread | entscheidung | GIL in `manifold3d` (14,1–14,6 s beim Übernehmen großer Verfeinerungen, 0,1–0,5 s beim ersten Verkleinern), Weg Hilfsprozess; dazu die genaue Vorschau der Senkplatte (4,3–5,7 statt unter 3 s) und die Abnahme auf ruhiger Maschine — auch der Changelog-Satz „grobe Vorschau in unter einer Sekunde“, den bohrung unter Last mit 0,9–1,2 s maß. | rest-vorschau-schluss.md:27; bohrung-schluss.md:25 |
| RM-258 | Beim Parsen großer 3MF steht der Hauptfaden bis 2 s | entscheidung | Freigabe für `py-spy` (MIT, nur Entwicklerwerkzeug), dann eine halbe Stunde messen. | fenster-schluss.md:22 |
| RM-251 | Mehrteilige Aufträge enden lokal am Schrittlimit | entscheidung | (a) Grenze 12 für den lokalen Weg ja/nein (23 gegen 22 von 39, im Rauschen); (b) Prompt-Satz ungemessen, zwei volle lokale Läufe je Stand; Suite nach `51c17b7a6` nicht neu gefahren. | ki-schluss.md:27 |
| RM-280 | Nach *Skalieren* bleibt die Kamera | entscheidung | Ob Skalieren unter Roberts Kameraregel vom 23.08.2026 fällt oder `frame_next_scene` auch nach einem Skalieren über den Rahmen hinaus rahmt (Organizer ×2,3: 52 % im Bild). | rest-kunde-schluss.md:22 |
| RM-131 | Mehrfachimport | entscheidung | Roberts Zurückstellung, unverändert. | fenster-schluss.md:28 |
| RM-271 | An einer Magnettasche heißt die Wahl „Senkung und Stufen mitnehmen“ | entscheidung | Name bleibt, oder anders an einer Kette mit Verengung (berührt Handbuch, `website/funktionen.html`, ältere Changelog-Einträge). | rest-lippe-schluss.md:6 |
| RM-229 | Geteilte Stücke heißen nach einem Buchstabenpfad | entscheidung | Nummerierung geteilter Stücke („Wandleiste B A · Stifte“); die Anordnung ist behoben. | druck-schluss.md:12 |
| RM-252 | Korpuslauf der Übergabe: ein Slicerfehler bleibt zu melden | extern | Absturz von ElegooSlicer/OrcaSlicer am zweifarbigen Besteckeinsatz bei Elegoo/Orca melden (`enable_support = 1`, `support_type = normal(auto)`); dazu Entscheidung, ob mehrfarbige Teile in der Orca-Familie auf Baumstützen ausweichen. | druck-antwort.md:22 |
| RM-016 | Agenten-Suite gegen das Vorgabemodell | extern | Gehosteter, kostenpflichtiger Lauf mit Roberts Freigabe. | ki-schluss.md:28 |
| RM-014 | Zusätzliche Formenregel | extern | Braucht denselben bezahlten Suitelauf vorher/nachher. | ki-schluss.md:28 |
| RM-213 | Fensterabnahme und Kundenwege am echten Fenster | release | Alle Fenstertests der Durchsicht im Release-Tor, darunter der schon vorher rote `test_the_measures_stay_in_the_view_while_a_pulled_slot_waits`; Bildschirmleser an den neuen Bedienelementen (auch das Fadenkreuz der Stellenwahl); Zeiten auf ruhiger Maschine (Laden, Vorschläge im Druckdialog, Erkennung großer Netze, Kanten verfeinern). | rest-auswahl-schluss.md:26; rest-klick-schluss.md:31; fenster.md:754; UEBERGABE.md:242 |
| RM-184 | Dateiaudit | release | Ablauf der Dichtnut am sichtbaren Fenster mit Bildern (Zeichnen, Öffnung, Gegenfläche, Übernehmen, Strg+Z); Kern und Verlauf sind belegt. | reparatur-schluss.md:43 |
| RM-232 | Klickkette an einem Merkmal | release | Abnahme 100 ms auf ruhiger Maschine am eingeschalteten MSI; gemessen 74–79 ms unter leichter Last am Ersatzbildschirm. | rest-klick-schluss.md:6 |
| RM-204 | Merkmalklick baut alle Handlungen neu | release | Nur noch `test_feature_panel.py` und `test_ui.py` im Release-Tor; die Zeit ist am echten Fenster erfüllt (massbild: 7,4–9,5 ms, Ziel unter 20 ms) — das Register nennt diese Messung nicht. | massbild.md:457 |
| RM-197 | Maßeditor im Bild | release | Abnahme am echten Fenster mit Hardware-Gefühl; massbild hat es ohne dieses belegt. | massbild.md:460 |
| RM-200 | Ein Zug am Griff soll flüssig sein | release | „Fühlt sich flüssig an“ am echten Fenster; die Zahlen (3–35 ms je Bewegung) liegen im Rahmen. | massbild.md:462 |
| RM-166 | Ergebnisnetze aus Mesh-Ops überstehen keinen Weld | release | `xfail(linux)` fällt nach drei grünen Linux-CI-Läufen in Folge; Beispielarchiv der Werkstattfilme mit der nächsten Filmrunde. | reparatur-schluss.md:41 |
| RM-055 | Neue Paketwerkzeuge im Kundenpaket | release | Den Signierprüfschritt (`73692bfbc`) am nächsten Installerlauf mit abweichendem Commit im Protokoll belegen. | werkzeuge-schluss.md:21 |
| RM-234 | Linux-Fensterabnahme und macOS-Gegenprobe | release | Nachweis der unabhängigen Meldung der Fensterverträge an einem echten Lauf. | werkzeuge-schluss.md:14 |
| RM-113 | Besitzerprüfung der Tokendatei auf dem Windows-Runner | release | Beleg auf dem CI-Runner; der Registertext sagt noch „das Repository ist nur beim Release öffentlich“, seit 27.09. ist es öffentlich (register.md:131–133). | werkzeuge-schluss.md:14 |
| CI-Testlaufzeiten | Vollständige Prüfungen früher abschließen | release | CI-08: Laufzeitgewinn am ersten abgeschlossenen Releaselauf mit der neuen Aufteilung. | werkzeuge-schluss.md:14 |
| RM-247 | Waschschüssel nach Solidons Übergabe | fremd | Probedruck am Centauri. | druck-schluss.md:17 |
| RM-228 | Lüfter und Spulen bleiben beim Hersteller | fremd | PLA-Vorgabe und Curas Schichtzeitschwelle (80 s heben den Lüfter in Schicht 1: Okarina 75 %, Würfel 92 %), Kammerlüfter, unbemalte Spulen alter Projekte. | druck.md:224, :281 |
| RM-257 | Kanäle frei halten auch für Cura | fremd | Curas Fenster bekommt die Sperre nicht (Stufe E von RM-281). | druck.md:282 |
| RM-250 | Brim je Teil beim Export | fremd | Zeile je Teil im Druckdialog und Schreiben je Teil (Stufe E von RM-281). | druck-schluss.md:16 |
| RM-164 | Creality Print rechnet über die Kommandozeile keine 3MF | fremd | Handprobe im Fenster (Sperre, Tempo, Brim), dann *Slicen* für Creality Print sperren oder über STL führen. | druck-schluss.md:9 |

---

## 3. Erledigt oder Hardware

57 Reste: `erledigt` 50, `hardware` 7. Gemeint sind Reste, die ein Bericht offen,
teilweise, als Registersatz oder „Für Nachbarn“ stehen ließ und die danach
belegt geschlossen wurden.

| Rest | Quelle | Kategorie | Beleg |
|---|---|---|---|
| Magnettasche aus dem Baustein: `pattern_feature` lehnt sie am exakten Körper an ihrer Lippe ab (samt Nachtrag BOHRUNG-13) | ki-schluss.md:34; KOORDINATION.md:106 | erledigt | `51c17b7a6` |
| Gedruckte Schraube meldet `feature.body_split`; schräg gesetzte Tasche halb zugedeckt | rest-bohrung-schluss.md:35; rest-lippe-schluss.md:41 | erledigt | `bba2c6ea7` |
| Magnettasche bei z = 0 ohne Befund in der Luft | bohrung-schluss.md:37 | erledigt | `3f087f7d6` |
| RM-248 Deckel einer gekrümmten Mündung | bohrung-schluss.md:32 | erledigt | `1880cb13d` |
| RM-259 in ebener Fläche (gekrümmt siehe Abschnitt 2) | rest-bohrung-schluss.md:26 | erledigt | `202d5133a` |
| RM-263 Tasche ohne Lippe kippt an den Kernen um 0,56 mm³ verschieden | rest-lippe-schluss.md:42 | erledigt | `2e496575b` |
| RM-264 *Zum Langloch ziehen* fragt am exakten Körper eine andere Erkennung | rest-lippe-schluss.md:43 | erledigt | `02b11be45` |
| Einlaufprofil einer Verengung (*Bohrung ändern* an der Lippe) | rest-erkennung-schluss.md:22 | erledigt | `8e1e3aca5`, `1e9f21d50` |
| Fasen eines Langlochs am exakten Körper | bohrung-schluss.md:34 | erledigt | `b465a72cc` |
| ERKENNUNG-04, R1 und R1-Rest: Rundformen am fein geteilten Netz nach einem formenden Schritt | erkennung-antwort.md:7; rest-erkennung-schluss.md:11 | erledigt | `a54dfcb4e`, `e805f511f` |
| R3: Haltelippe heißt „Senkung“ | erkennung-schluss.md:6 | erledigt | `63daa4d63` |
| R4: welches Stück einer geteilten Fläche den Namen erbt | erkennung-schluss.md:6 | erledigt | `5478f5673` |
| `perceive.orphaned` für `face_6` nach einer Bohrung über die Kante (ERKENNUNG-13) | texte-schluss.md:36 | erledigt | `1afc1852d` |
| RM-267 Verbindernummern des Auto-Split zählen erkannte Zapfen mit | erkennung-schluss.md:36 | erledigt | `6f7eafc25` |
| RM-253, Teil KUNDE-10: *Modell teilen* scheiterte am Laptop-Ständer | bohrung-schluss.md:36 | erledigt | `f58ef38ca` (Geometrie siehe Abschnitt 2) |
| DRUCK-10 Tempo für Drucker ohne Eintrag (RM-255) | druck-schluss.md:11 | erledigt | `aed31c787`, `44ab90965` (Archiv RM-255) |
| DRUCK-11 ältere Projekte behalten 40 mm/s (RM-256) | druck-schluss.md:11 | erledigt | `aed31c787` (Archiv RM-256) |
| RM-229, Teil Anordnung: Teil, das nur ohne Rand passt | druck-schluss.md:12 | erledigt | `58e654ac5` (Nummerierung siehe Abschnitt 2) |
| RM-231 Fehlerbericht aus dem Fenster ungeschwärzt | register.md:58; rest-kunde-schluss.md:8 | erledigt | `c3271ecd8` |
| RM-268 Knöpfe an Befunden verbrauchter Körper | reparatur.md:658; register.md:82 | erledigt | `8615dc1e6` |
| RM-269 vier Kleinigkeiten vom Kundenweg samt Frage KUNDE-08 (Menü *Erzeugen* doppelt: gewollt) | kunde.md:703; massbild.md:504 | erledigt | `3eef03427`, `6bcffec39`, `9f821c70c`, `66ba71ba5` |
| RM-270 Katalogkollision „Tasche“ | texte-schluss.md:29 | erledigt | `bd33620c5` |
| Knöpfe in Zitaten: 139 abweichende Sätze (RM-084-Anteil) | texte-schluss.md:17, :29 | erledigt | `e8f9f574d` (37 berichtigt, Rest begründete Ausnahme, Wächter) |
| RM-088 Konstrukteurswörter in Kundentexten | texte-schluss.md:15 | erledigt | `e8f9f574d` |
| RM-215 Befundstellen ohne Handlung; `join.blocked`; Variantendialog ohne Rat; `fit.*` und Druckbefunde ohne Knopf | texte-schluss.md:13, :17; texte.md:325 | erledigt | `e8f9f574d`; Nachträge `6b5650dad`, `ce8b91c7c` |
| `decimate_first` ohne Handler | reparatur-schluss.md:44 | erledigt | `8b6af9220` |
| RESTVERLAUF-04 Vorschau von *Kanten verfeinern* über zehn Minuten; `remesh_first` bei *Glätten* | rest-verlauf-schluss.md:22; rest-verlauf.md:366 | erledigt | `ce8b91c7c` |
| RESTVERLAUF-05 Rest: `body.faces[…]` in Schleifen | rest-verlauf-schluss.md:21 | erledigt | `501fdfbb3` |
| Kundenprüfer-Registersätze: Modell zuerst, Urteil „Druckbereit“ | kunde-schluss.md:16 | erledigt | `fa0320fe7`, `6217c57f9`, `3b57b3644` |
| KUNDE-01 bis KUNDE-15, an die Gebiete verteilt | kunde-schluss.md:3–12; KOORDINATION.md:49, :53 | erledigt | u. a. `22a2a20ad`, `4c8eae019`, `5a90d4361`, `c2ebc0fe0`, `12b7e9174`, `f58ef38ca`, `5948a79a5`, `8c3a9d702`, `3b57b3644`, `fa0320fe7` |
| Kleinere Beobachtungen des Kundenprüfers: toter Eintrag nach verschobener Datei, Außenkante mit Nummern, Frage vor der Vollerkennung (zwei Knöpfe, *Abbrechen* bewusst behalten) | kunde.md:703–714 | erledigt | `fa0320fe7`, `5a90d4361`, `c2ebc0fe0` |
| Schnittstelle „erst das Modell, dann die Merkmale“ und die angekündigte Anpassungszeile | erkennung-schluss.md:34; fenster-antwort.md:11 | erledigt | `fa0320fe7` |
| FENSTER-10 Rest: Stellensuche sagt „zu viele Dreiecke“ erst nach der Rechnung (RM-265) | fenster.md:943; register.md:79 | erledigt | `53e816290` |
| Arbeiterkopien erben die Flächenfits nicht | massbild.md:506 | erledigt | `69426aae9` |
| Kopf des Auswahlfensters bei gewählter Kante | massbild.md:502 | erledigt | `3eef03427` |
| RM-232 Zwischenstände: Filter, Soforttakt, Renderer-Elemente, Maßgruppe, Pickrückfrage | rest-leistung-schluss.md:16; UEBERGABE.md:146 | erledigt | `d8b48f569`, `f01f8b622`, `0273b8d23`, `c2bff45f1` (Abnahme siehe Abschnitt 2) |
| Nach Klick auf die Mitte der gewählten Bohrung wechselt die Auswahl nicht mehr | UEBERGABE.md:161; rest-klick.md:466 | erledigt | `962c63cf0` |
| REST-BOHRUNG-07 örtliche Nachmessung endet an großer gekrümmter Fläche | rest-bohrung-schluss.md:16 | erledigt | `84aa9a5aa` |
| `detect_known` stellt Ganzkörperfragen | bohrung-schluss.md:35 | erledigt | `84aa9a5aa`, `501fdfbb3` |
| Exaktes Volumen im UV-Rückfall (33 s an gs-100) | bohrung-schluss.md:36 | erledigt | `b0d344e5c` |
| RM-260 `on_surface` baut Suchbäume je Aufruf | rest-bohrung-schluss.md:28 | erledigt | `450067ead` |
| RM-261 volle Erkennung nach jedem Schritt (rund 30 s) | rest-bohrung-schluss.md:33; rest-erkennung2-schluss.md:33 | erledigt | `e6e6f3ba0`, `e1b897ca2` |
| RM-266 *Modell teilen* 51 s in der Stützschätzung | reparatur.md:680; register.md:80 | erledigt | `1d8dd68aa` |
| RM-214 Bereichsprüfung ohne Index und Wächter; vtk noch in der `.venv` | werkzeuge-schluss.md:7–8 | erledigt | `7e3442623`, `a0db3edeb`; vtk entfernt (KOORDINATION.md:51) |
| Signierweg: Testschritt bei abweichendem Baucommit | werkzeuge-schluss.md:12; UEBERGABE.md:202 | erledigt | `73692bfbc` (Beleg am Runner siehe RM-055) |
| Ganze Suite am zusammengeführten Stand (angehaltene `affected_tests`-Läufe) | reparatur-schluss.md:40; ki-schluss.md:48; druck-schluss.md:62 | erledigt | Entwicklungstor je Übernahme grün (KOORDINATION.md:80–160) |
| Bereichsnachweis nach allen Übernahmen neu | KOORDINATION.md:55, :178 | erledigt | `3193db703` |
| `ROADMAP-ARCHIV.md` endet mit einer Leerzeile zu viel | UEBERGABE.md:163 | erledigt | `ca1de12f3` |
| Changelog-Vorschläge der zweiten und dritten Runde | register.md:124–127; alle Schlussberichte der Runde 3 | erledigt | `098fc2019`, `46fa73c17` (als Auswahl nicht aufgenommen: exaktes Volumen in 1,5 s, Drache 3 statt 6 s, Passungen an Stiften beim Teilen) |
| `wt-kunde050` entfernen; Platzhalter im ast-flake-Bericht | kunde-schluss.md:18; register.md:128 | erledigt | beides am 27.09. nicht mehr vorhanden (geprüft) |
| RESTVORSCHAU-08: `NameError: name 'type'` in `perceive/local._plain`, danach Segfault nach `os._exit` | rest-vorschau-schluss.md:25; UEBERGABE.md:155 | hardware | ast-flake.md:44 (dieselbe Familie), `bd862bf34`, RM-272 |
| Absturz beim Einlesen einer 3MF (`threemf._native_tools_of`, `NameError: NUMBER_BLOCK`), Verdacht `gc.freeze` | rest-bohrung-schluss.md:30; UEBERGABE.md:153 | hardware | ast-flake.md:44 (`gc.freeze` für diese Fehlerart nicht nötig), RM-272 |
| Absturz beim Laden des Gartenschlauchhalters (Exit 139, einer von 19) | rest-erkennung2-schluss.md:57 | hardware | RM-272 |
| Pre-Commit-Hook: `TypeError … str_ascii_iterator` in `test_language_rules[prepare_ops.py]` | UEBERGABE.md:159 | hardware | ast-flake.md:9–34, RM-272 |
| `ast.walk`-TypeErrors in `test_language_rules`; Exit 139 der Wächterfamilie bei rest-lippe | UEBERGABE.md:156; rest-lippe-schluss.md:48 | hardware | `bd862bf34` (Ursache CPU, kein Code geändert), RM-272 |
| Einzelner Abriss (Exit 139) in einem Korpuslauf von rest-teilen | rest-teilen-schluss.md:33 | hardware | RM-272 |
| Zwei Pflaster, die seit August einen Fehlschlag wiederholen (`geom/mesh.on_surface`, `export/threemf._numbers_from`), helfen nur auf dieser Maschine | ast-flake.md:212–214 | hardware | RM-272 (kein Arbeitsauftrag genannt) |
