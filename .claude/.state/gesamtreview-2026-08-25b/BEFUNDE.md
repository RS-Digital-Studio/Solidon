# Gesamtreview Solidon — 25.08.2026 (unabhängiger Durchgang)

**Auftrag:** Gründlicher Review der gesamten Anwendung anhand des Ist-Codes — nicht der
Dokumentation. Auf Roberts Anweisung unabhängig vom vorhandenen Ordner
`gesamtreview-2026-08-25/` (nicht gelesen, nicht benutzt).

**Vorgehen:** Dreizehn strikt lesende Review-Agenten, je Gebiet einer, mit der Auflage,
Befunde am ausgeführten Code zu belegen (VERIFIZIERT = ausgeführt/nachgerechnet,
PLAUSIBEL = nur gelesen). Dazu ein vierzehnter für die Website aus Kundensicht.
Register in `ROADMAP.md` gegengelesen — dort geführte Punkte sind nicht erneut
aufgeführt. Gestartet auf b1766c28; parallele Sitzungen haben während des Reviews
teils schon Fixes gebaut (Flächenmenü u. a.).

**Gebietsberichte:** je Gebiet eine Datei unter `berichte/`.

**Zählung:** rund 90 Codebefunde, davon **34 hoch**. Fast alle am ausgeführten Code
belegt, oft mit Messwert. Elf von vierzehn Gebieten enden mit „Kann das so rein: nein".

---

## Die schwersten Befunde — Kunde bekommt falsche Geometrie, verliert Daten oder Geld

**Geometrie, die stumm falsch herauskommt:**
1. **Bohren/Stopfen entscheiden die Richtung am Hüllquader** — an gestuften Teilen bohrt eine Sackbohrung in die Luft (0,28 statt 169,65 mm³, kein Befund); ein Stopfen wird zum Zapfen. Zwilling des Senkungs-Fixes vom 25.08., der `drill`/`plug` übersprang. [Geometrie 2]
2. **Ein durchgehender Stopfen ab der Mündung füllt nur die halbe Bohrung** — `plug()` fehlt der `*2.0`-Faktor, den `drill()` hat. [Geometrie 1]
3. **Die Gewindenut frisst die Decke des Drehdeckels** — bei der Vorgabesteigung bleibt eine 7-µm-Decke, ab pitch 4 ist der Deckel offen (Loch 22–65 mm²). [Geometrie 3]
4. **Das Würfelgitter setzt Stäbe außerhalb des Teils ab** — 33 frei schwebende Balken, Außenmaß +22,5 statt +20. [Geometrie 4]
5. **Ein andersherum gezeichnetes Loch wird addiert statt abgezogen** (B-Rep) — zwei von vier Klickreihenfolgen liefern +67 % Volumen, ohne Befund. Betrifft extrude/revolve/sweep. [Skizze 1]
6. **„Tasche schneiden" verliert jedes gezeichnete Loch** — `shifted()` fehlt `holes=`, die Insel wird mitweggefräst. Zwilling des Loft-Fixes. [Skizze 3]
7. **Zwei sich kreuzende Umrisse ergeben ein undichtes Netz ohne Wort** — geht in Export und Schichtanalyse. [Skizze 2]
8. **`feature:face_N` ist eine Positionsnummer, keine stabile ID** — eine Bohrung darunter lässt die Skizzenebene auf eine andere Fläche springen (Aufsatz wandert vom Deckel in die Seitenwand). [Skizze 4]
9. **„Verlängern" kürzt die Linie um die Hälfte** — Umkehrung des Trim-Fixes. [Skizze 5]
10. **„Auf diese Breite skalieren" misst die falsche Zeichnung** — eine Hilfslinie im DXF macht aus 50 mm ein 5-mm-Teil. [Import/Export H1]
11. **Beim Export überschreiben sich gleichnamige Objekte** — eine Datei, zwei Erfolgsmeldungen, ein Teil weg. [Import/Export H2]
12. **Mesh- und B-Rep-Bohrung bohren bei Vorgabe in entgegengesetzte Richtungen** — `MENU_TWINS` ist dann kein Umschalten. [Skizze 10]

**Datenverlust und Lizenzgrenze:**
13. **Cache-Schlüssel deckt fremde Objekte nicht** — nach dem Wiederöffnen zeigt der Cache falsche Geometrie (ausgerichteter Körper an der alten Lage, `up_to` auf alter Höhe). [Szene 1]
14. **Drei Dokumentänderungen kommen ohne Freischaltung durch** — nach Ablauf der Demo bleibt jeder Schritt umparametrierbar; das Projekt lässt sich vollständig umkonstruieren und speichern. [Szene 2]
15. **`Feature.recognised` überlebt den Plattencache nicht** — benannte Baustein-Bohrungen verwaisen aus dem warmen Cache. [Szene 3]
16. **Nachträgliche Parameteränderung ist nicht rücknehmbar** — Strg+Z trifft einen anderen Schritt, der alte Wert ist weg. [Szene 5]
17. **Geändertes Projekt geht beim Einfügen vom Startbildschirm ohne Frage verloren** — STL ziehen nach *Datei → Neu* ersetzt Dokument und History. [UI-Fenster 1]
18. **`_exporting` wird nie gesetzt** — der Fortschrittsbalken verschwindet, während der Export noch schreibt; der Kunde schließt das Fenster. [UI-Fenster 3]

**Freischaltung und Support (trifft den ausgelieferten Stand):**
19. **Eine falsch gestellte Uhr beendet Demo und Testlauf dauerhaft** — ein Start mit Datum in der Zukunft verbrennt die Frist, auch wenn die Uhr danach stimmt; schlimmster Fall leere BIOS-Batterie beim ersten Start. Und die Kehrseite: frischer Rechner mit Uhr 2020 → 2495 Tage Demo. [Infra 1, 3]
20. **Jede Absage der Gegenstelle kommt als „nicht erreichbar" an** — bei der NAT-Ratengrenze (429) heißt der primäre Vorschlag *Noch einmal senden*, was die Sperre verlängert. [Infra 2]
21. **Beschädigte Installation: der zahlende Kunde soll kaufen** — bei Integritätsfehler wird der gültige Schlüssel nicht gelesen; „Testzeitraum abgelaufen". [Infra 5]

**Schichtanalyse (Beratung, die der Kunde annehmen soll):**
22. **Die Orientierungssuche stellt flache Teile hochkant** — eine 0,4-mm-Karte wird 54 mm aufgestellt (leere Schichtliste). [Schicht 1]
23. **Auto Split lässt tote Passungen im Dokument** — zwei Schnitte → zwei `fit.missing_feature`-Fehler im Prüfbericht. [Schicht 2]
24. **Auto Split liefert ein Stück über der Bettgrenze** — der Stiftüberstand wird nicht eingerechnet (223 mm auf 216-mm-Bett). [Schicht 3]

**Sicherheit / Agentenschicht:**
25. **OpenSCAD-Quelltextprüfung mit einem Kommentar umgehbar** — `import /*x*/ ("<absolut>")` fällt durch beide Muster; `surface` liest jede Textdatei. Ein Modellzug startet OpenSCAD schon vor jedem Klick. [Agent 1]
26. **Ein Rezept, das ein Rezept einsetzt, kommt an allen drei SCAD-Sperren vorbei** — Fernaufruf-DENY, auto_acceptable und §32-Warnung fallen gemeinsam. [Agent 2]
27. **Ein angenommener Vorschlag kann auf einen fremden Körper wirken** — neu vergebene Objekt-IDs; die Bohrung landet im inzwischen angelegten Zylinder. [Agent 3]
28. **Fremder Text aus einer Projektdatei steht ungerahmt im Werkzeugblock des Modells** — Prompt-Injection über den `doc`-Text eines mitgereisten Rezepts, an der Stelle höchster Autorität. [Agent 4]

**Dialoge, die Daten dauerhaft ändern:**
29. **Drucker-/Materialwechsel wirft die Druckeinstellungen des Projekts weg** — 62 % Füllung → 15 %, ohne Ansage. [Dialoge 2]
30. **Slot-Filamentwahl kommt nie beim Slicer an** — der Anzeigetitel „(eigenes)" statt des Profilnamens wird gespeichert, sprachabhängig. [Dialoge 3]
31. **Parameterleiste schneidet gemessene Zehntelwerte ab** — 0,075 → 0,07, Drehknopf springt auf 1,07. [Dialoge 4]
32. **„Erzeugen" ist klickbar und tut wortlos nichts** — bei laufendem ComfyUI ohne eingerichtete Knoten. [Dialoge 1]

**Wahrnehmung / Bausteine (falsche Teile):**
33. **Die Mutternfalle schneidet keine Mutterntasche** — nur ihr Schraubenloch; die Tasche liegt über der Mündung in der Luft. Siebter `MOUTH_AT_ORIGIN`-Zwilling. [Wissen 1]
34. **`screw_hole`: die Kopffreiheit tut nichts** — der Zylinder liegt über der Mündung; der Schraubenkopf steht vor. [Wissen 2]

Dazu **Sicherungsnetz:** die §38-Isolation greift auf macOS nicht (die Suite schreibt ins echte Profil), und `test_errors.py` sieht 5 von 25 Fehlerklassen nicht — beide decken eine harte Regel nur scheinbar. [Tests 1, 2]

---

## Das durchgehende Muster: der reparierte Fehler mit Zwilling

Der häufigste Befundtyp im ganzen Review: ein Fehler wurde an einer Stelle behoben, die
baugleiche Nachbarstelle blieb. Belegte Zwillinge, quer durch alle Gebiete —
Senkung → Bohren/Stopfen (Geom 2), Loft → Tasche (Skizze 3), Trim → Extend (Skizze 5),
`created_by` → `recognised` (Szene 3), Namensvergleich → verschachteltes Rezept (Agent 2),
`_on_split_done` → `_on_agent_done`/`_survey_done` (UI-Fenster 5/6), `catalog`-Knopf →
`generate`-Knopf (Dialoge 1), `RecipeDialog.saved` → `support_dialog._sent` (Dialoge 5),
`_op_title` im Verlauf → im Chat (Dialoge 6), sechs `MOUTH_AT_ORIGIN`-Bausteine → `nut_trap`
(Wissen 1), `discover`/`cli` → `report.write` (Infra 7), 3MF-Baugruppe → Einzelkörper (I/O G2),
Alt-Text „ways" (Doku 3). **Empfehlung: nach jedem Fix die Geschwister mitsuchen** —
genau das steht schon in der Memory-Notiz [[reparierter-fehler-hat-zwillinge]].

---

## Website (Kundensicht — Umsetzung läuft bei 3d-druck-a2)

Starke Substanz (schmerzgetriebene H1, Ehrlichkeitsblock, keine Cloud/Telemetrie), aber
zwei dringende Fehler: Zwölf Unterseiten und der statische Stand aller sechs Startseiten
erzählen noch „Die Demo **erscheint** am 20. August 2026" (Zukunftsform, fünf Tage nach dem
Erscheinen, für jeden Crawler und JS-Blocker sichtbar); der Update-Hinweis auf der
Startseite ist seit 0.1.5 falsch; das Aufmacherbild zeigt einen Prüfbericht mit drei
Fehlern am eigenen Modell. Voller Katalog (acht Schnellgewinne, fünf größere Hebel) in
`berichte/00-website.md`.

---

## Zwei Dinge, die keinen Code betreffen

- **Ungestagte Löschung von 199 Dateien unter `.claude/.state/`**, darunter das Tor-Skript
  `suite-getrennt.sh` (laut CLAUDE.md der einzige Weg, auf dem die Suite durchläuft). War
  nicht dieses Review (strikt lesend, nur neu geschrieben). 3d-druck-ce hat `suite-getrennt.sh`
  aus HEAD wiederhergestellt; der Rest liegt gelöscht. **Ein `git add -A`/`commit -a` nimmt
  die Löschung mit — nur mit Pfaden committen.**
- **`3D Drucker/` liegt nur auf einer Maschine** (458 MB, kein Remote) — steht im Register,
  bleibt ein Datenrisiko.

---

## Empfehlung zur Reihenfolge

1. **Vor der nächsten Auslieferung** (Kunde erlebt es als Fehler oder Datenverlust): die
   Geometrie-Zwillinge (1–12), die Datenverlust-Fälle (13–18), die Freischaltungs- und
   Support-Fehler (19–21), die vier Sicherheitsbefunde der Agentenschicht (25–28), die
   dauerhaft ändernden Dialoge (29–31).
2. **Unmittelbar danach**: die Beratungsbefunde der Schichtanalyse (22–24 + die mittleren),
   die Bausteinausfälle (33–34), die zwei Sicherungsnetz-Lücken.
3. **Geplant nachziehen**: die zahlreichen Doku-/Text-/i18n-Befunde (je ein Einzeiler plus
   Übersetzung) und die Handwerksbefunde.

Jeder hohe Befund ist einzeln klein (die meisten unter dreißig Zeilen) — die Menge, nicht
die Tiefe, ist die Arbeit.
