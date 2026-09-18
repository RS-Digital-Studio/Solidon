# CAD für Druckteile: vertiefte Prüfung von Erkennung und Bedienung

Stand: **18.09.2026, Anwendungscode `2148ddfa`**. Ergänzung zum
[CAD-Konzept](konzept-vollwertiges-cad-2026-09.md), insbesondere §§3–11 und 13.
Die 16 Entscheidungen dort bleiben bestehen. Roberts anschließende Antwort
„alles“ nimmt auch sämtliche Ausbauideen aus §6 in den Auftrag auf; die
Zuordnung steht im Konzept §§13.8–13.9 und §14.2. Diese Recherche ergänzt
Nachweise und Abnahmen; sie startet keine Umsetzung vor Veröffentlichung von
0.4.3. Offene Arbeit: [RM-188](../ROADMAP.md#rm-188), Nachbau:
[RM-022](../ROADMAP.md#rm-022).

## 1. Ergebnis und Prioritäten

**Die Grundlage ist breit, die durchgängige Gleichwertigkeit noch nicht erreicht.**
132 registrierte Operationen, 35 Bausteine und 12 Merkmalsarten ersetzen
keinen vollständig geprüften Kundenweg. Insbesondere ist „gültiger exakter
Körper“ kein Beleg, dass Solidon seine geometrischen Merkmale erkennt.

| Priorität | Was für das beschlossene Ziel fehlt | Nachweis / Abnahme |
|---|---|---|
| 1 | Merkmale nach Änderungen richtig erhalten | Spiegelung verliert B-Rep-Merkmale; Skalierung erzeugt doppelte Flächen mit alten Flächeninhalten (§2) |
| 1 | Importierte Form unabhängig von ihrer Darstellung erkennen | Gültige NURBS-Platte mit Bohrung bleibt auch nach STEP-Rundreise ohne Merkmale (§2.1) |
| 1 | Maße und tatsächliche Passung auseinanderhalten | Polygonloch und Zapfen können trotz positiver Durchmesserdifferenz kollidieren; Konzept §4 |
| 1 | Dieselbe Handlung mit derselben Wirkung auf beiden Körperarten | Aushöhlen, Skalieren, Merkmalsänderung und 31 bislang konvertierende Bausteinpfade; Konzept §§5, 10, 13 |
| 2 | Vollständige Merkmalsfamilien und zusammengesetzte Formen | Torus, Freiform, Innenraum und importierte Gewinde auf B-Rep; Senkung, Teilöffnung und Schnittbohrungen nicht nur als einzelne Trägerflächen betrachten |
| 2 | Verlässliche Referenzen und Skizzenanschlüsse | Außenflächenprojektion, Bezugsebenen, Kantenaufteilung und verlorene Referenzen; Konzept §§6, 13.3 |
| 2 | Verständliche direkte Bearbeitung | Eindeutige Hauptaktion, Maßherkunft, nachvollziehbare Auswahl und erklärtes Nichtkönnen (§4) |
| 3 | Nachbau als bearbeitbare Operationsfolge | Geprüfter Kandidat hinter dem Import, lokale Formtreue, Topologie, Grenzen und Rückweg; Konzept §13.5 |

„Vollwertig“ bleibt auf Konstruktion von Druckteilen bezogen. Baugruppen,
Zeichnungsblätter, FEM, Cloud, lernende Geometrieverfahren und ein neuer Slicer
werden durch diese Recherche nicht zu Anforderungen. Eine verlässliche
Änderung eines importierten Lochs bringt dem Ziel mehr als ein zusätzlicher
Befehl ohne passende Auswahl, Maßführung und Fehlerbehebung.

## 2. Neue reproduzierte Lücken

### 2.1 Analytische Form als NURBS: im exakten Kern unsichtbar

Prüfkörper: `edit.box(40, 30, 10)` mit `edit.cut_bore`, Ø6 mm, Tiefe 20 mm,
Position `(0, 0, 5)`, Richtung `(0, 0, 1)`. Danach
`BRepBuilderAPI_NurbsConvert(shape, True)` und Solidons eigener STEP-Schreib-
und Leseweg. `BRepCheck_Analyzer.IsValid()` meldet in allen drei Fällen gültig.

| Darstellung | `brep.features.features_of` |
|---|---|
| Analytischer Ausgangskörper | 6 Flächen, 1 Bohrung Ø6 |
| In NURBS umgewandelt | keine Merkmale |
| NURBS über `step.write` → `step.read` | weiterhin keine Merkmale |

Die Netzerkennung auf der Tessellierung findet am NURBS-Körper dagegen sechs
Flächen und eine Bohrung, gemessen Ø5,9893 mm. Sie beweist weder exakte
Maßrückgewinnung noch die richtige B-Rep-Referenz. Eine solche Erkennung darf
nicht ungeprüft als exakte Topologie ausgegeben werden.

Ursache: [features.py](../app/core/brep/features.py) beschreibt analytische
Ebenen, Zylinder, Kegel und Kugeln; die analytische Form einer B-Spline-Fläche
wird dabei nicht zurückgewonnen. **Freiformerkennung allein genügt nicht:**
Eine als NURBS dargestellte Ebene muss weiterhin als Ebene bearbeitbar sein.

Für P2.3 zuerst geometrische Klassifikation innerhalb eines festgelegten
Fehlerbudgets prüfen. Eine reine Leseanalyse darf die importierte Form nicht
heimlich ersetzen. Falls eine kanonische Umwandlung nötig ist, entsteht der
neue Körper über eine reproduzierbare Operation mit Zuordnung und Undo.
Bei unsicherem Ergebnis bleiben Original und verständliche Grenze erhalten.

**Die vertiefte Bibliotheksprobe liefert bereits einen Ansatz ohne neue
Abhängigkeit:** Das installierte OCCT erkennt am selben NURBS-STEP-Körper
sechs Ebenen und den Ø6-Zylinder (§5.2). Der Ausfall liegt für diesen
Prüfkörper im Solidon-Anschluss, nicht in fehlender Kernfunktionalität.

Minimaler Nachweis, im Repo mit der `.venv` ausgeführt:

```python
from collections import Counter
from app.core.brep import edit, step
from app.core.brep.kernel import Solid
from app.core.brep.features import features_of
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from OCP.BRepCheck import BRepCheck_Analyzer

body = edit.cut_bore(
    edit.box(40, 30, 10),
    position=(0, 0, 5),
    direction=(0, 0, 1),
    diameter=6,
    depth=20,
)
nurbs = Solid(BRepBuilderAPI_NurbsConvert(body.shape, True).Shape())
for current in (body, nurbs, step.read(step.write(nurbs))):
    print(
        BRepCheck_Analyzer(current.shape).IsValid(),
        Counter(f.kind for f in features_of(current).values()),
    )
```

### 2.2 Skalieren erhält veraltete Maße und erzeugt Doppelmerkmale

Vollständiger Auswertungsweg: `Document` → `History` → `evaluate`, Profil
Centauri Carbon 2 / PETG, Qualität `fine`. Quader 40 × 30 × 10 mm, einmal
`create_box`, einmal `create_brep_box`, danach die jeweilige Operation.

| Schritt | Netz-Eingang | B-Rep-Eingang |
|---|---|---|
| Spiegeln X | 6 Flächen, Netz | **0 Merkmale**, weiterhin B-Rep |
| Gleichförmig auf Faktor 2 skalieren | **12 Flächen**, Netz | **12 Flächen**, zu Netz geworden |
| X auf Faktor 2 skalieren | **10 Flächen**, Netz | **10 Flächen**, zu Netz geworden |
| Größte Abmessung auf 50 mm setzen | **12 Flächen**, Netz | **12 Flächen**, zu Netz geworden |

Alle Auswertungen endeten ohne angehaltenen Schritt. Der gleichförmig
skalierte Quader hat geometrisch weiterhin sechs Seiten. Frisch erkannte
Flächen tragen 1200, 1600 und 4800 mm², jeweils zweimal. Gleichzeitig
mitgeführte Flächen tragen die alten 300, 400 und 1200 mm² an den bereits
verschobenen Mittelpunkten. Das ist ein Fehler im gemeinsamen
Merkmalsvertrag, nicht nur eine fehlende exakte Skalierungsoperation.

[matching.moved_features](../app/core/perceive/matching.py) ist ausdrücklich
für starre Bewegungen geschrieben: Es verändert Punkte und Richtungen, keine
Durchmesser oder Flächeninhalte. Der Transformationspfad in
[evaluate.py](../app/core/scene/evaluate.py) braucht deshalb eine Unterscheidung
zwischen starrer Bewegung, gleichförmiger Skalierung und allgemeiner affiner
Änderung. Für nicht gleichförmige Transformationen gilt außerdem der
Normalenvertrag über die inverse transponierte Matrix; ein Kreis kann zur
Ellipse werden. Alte Bohrungsmaße dürfen dann nicht unverändert weiterleben.

Abnahme P2.1: genau sechs eindeutige Seiten mit korrekten Flächeninhalten,
gültige Referenzen, richtige Maße, kein ungeklärtes Doppelmerkmal; zusätzlich
Bohrung, Kugel, schräg stehende Fläche, negative Spiegelung und anisotrope
Skalierung. Die Box-Sonde belegt noch nicht sämtliche genannten Gegenfälle.

### 2.3 Torus und Operationsergebnis getrennt prüfen

Ein gültiger OCCT-Torus mit Haupt-/Nebenradius 15/3 mm liefert keine
B-Rep-Merkmale. Die Netzerkennung findet einen Torus (gemessener Durchmesser
29,9635 mm); `actions_for` liefert dafür keine Merkmalsaktionen. Damit fehlen
zwei Anschlüsse: Erkennung und direkte Bearbeitung. Körperoperationen bleiben
trotzdem verfügbar. Die Netzprobe meldete zusätzlich zwei Flächen; deren
fachliche Richtigkeit wurde hier nicht abschließend untersucht.

Kontrollfälle an beiden Quadern: Verrundung und Fase mit 1 mm sowie
Entformung mit 2° liefen durch; beim B-Rep-Eingang blieb der exakte Körper
erhalten. Wulst mit 1 mm wurde zum Netz. Ein `as_mesh_data`-Aufruf oder die
rohe `OpResult`-Kennzeichnung allein ist kein ausreichender Verlustnachweis;
maßgeblich ist das fertig ausgewertete Szeneobjekt.

## 3. Erkennung als gemeinsame fachliche Schicht

Der Zielvertrag braucht vier getrennte Angaben: **welche Form**, **welche
Maße**, **welche Qualität des Nachweises** und **welche Handlung**. Ein
Merkmal darf gefunden sein, ohne für jede lokale Änderung ausreichend
abgegrenzt zu sein. Das erklärt die Oberfläche am betroffenen Maß oder
Befehl, ohne eine Betriebsart „Netz/Exakt“ einzuführen.

Die folgende Kette ist ein Entwurf für den Ausbau, keine Behauptung über
bereits vorhandene APIs:

1. **Eingang prüfen:** Einheiten, Maßstab, Orientierung, Komponenten,
   Randkanten und ungültige Geometrie. Reparatur als eigener nachvollziehbarer
   Schritt, keine unbemerkte Formänderung zur besseren Erkennungsquote.
2. **Geometrische Bereiche bilden:** am Netz über Nachbarschaft und
   Normalen/Formabweichung; am B-Rep über Trägerflächen, Nähte und Trimränder.
   Analytische B-Splines innerhalb des Fehlerbudgets klassifizieren.
3. **Formhypothesen prüfen:** Ebene, Zylinder, Kegel, Kugel, Torus, Freiform;
   lage-, skalierungs- und triangulierungsunabhängig. Ein RANSAC-Treffer ist
   eine Hypothese, noch keine Bohrung.
4. **Fachliche Merkmale bilden:** Innen-/Außenseite, Nachbarschaft, Öffnung,
   Achse und Materialseite ergeben Bohrung, Zapfen, Senkung, Langloch,
   Tasche oder Gewinde. Schnittbohrungen, Teilzylinder und Nähte ausdrücklich
   mitprüfen. Vorhandene Langlochgruppierung daran anschließen.
5. **Referenzen nachführen:** Erzeugerprovenienz, OCCT-Änderungshistorie und
   geometrische Zuordnung kombinieren. Mehrdeutigkeit offen behandeln;
   Flächenindex, Weltkoordinatenhash und Nachbarschaftsgraph sind allein keine
   dauerhaft stabile Kennung.
6. **Handlungen anbieten:** gemeinsamer Parametervertrag, passende Vorschau,
   Abbruch, ein Undo, neue Prüfung. Unveränderliche Restbereiche bleiben
   erhalten; ein lokales Loch benötigt nicht zwingend einen vollständigen
   parametrischen Nachbau des ganzen importierten Teils.

Drei Fehlerbudgets getrennt führen: Abweichung der vorliegenden Geometrie,
Unsicherheit des erkannten Maßes und Fertigungsspiel aus dem Materialprofil.
Die Schichthöhe ist kein Ersatz für eine radiale Formtoleranz. Ein bewusstes
Vieleck darf nicht automatisch zum Kreis werden; Normgröße und ursprüngliche
Konstruktionsabsicht sind aus einer STL nicht allgemein eindeutig bestimmbar.

## 4. Oberfläche und Bedienung

### 4.1 Am nativen Windows-Fenster beobachtet

Separates temporäres Benutzerprofil; vorhandene Nutzereinstellungen wurden
nicht geändert. Tatsächlicher Startbildschirm, Import und GPU-Ansicht wurden
geöffnet, keine Handbuchabbildung als Beleg verwendet. Fenster zunächst
1282 × 852, später maximiert 2560 × 1392 Screenshot-Pixel; das ist **kein
Nachweis einer bestimmten DPI-Skalierung**.

| Schritt | Beobachtung | Bedeutung |
|---|---|---|
| Neuer Benutzer startet | Einführungsseite priorisiert Drucker/Slicer; Startseite bietet Import und neues Modell | Für das Konstruieren einen direkten Einstieg erhalten; Druckeinrichtung erst verlangen, wenn der Weg sie benötigt |
| `plate_holes.stl` öffnen | Ladefortschritt mit Abbruch, Platte 80 × 50 × 8 mm, vier Bohrungen und sechs Flächen | Import und erste Erkennung nativ bestätigt |
| In der Nähe einer Bohrung klicken | Zuerst Körper, am Rand eine Kante, weiter innen die Bohrung; Hover zeigte zeitweise bereits die Bohrung | Auswahlpriorität und Hervorhebung zusammen abnehmen; keine Klickzahlgarantie aus dieser Probe |
| Bohrung gewählt | Ø5,19 mm, Gewindehinweis M5, mehrere Handlungsgruppen gleichzeitig | Maßherkunft und Vorschlag dürfen nicht als bekanntes ursprüngliches Nennmaß erscheinen |
| Merkmalfenster | **19 fachliche Eingabefelder**: Verschieben 3, Ändern 6, Langloch 5, Drehen 2, Verdoppeln 3 | Die frühere Angabe 36 war keine belastbare Zählung eigenständiger Eingaben |
| Fokus wechselt zum Durchmesser | Hauptaktion wechselt von „Merkmal verschieben“ zu „Bohrung ändern“ | Umschaltung funktioniert; ihre Abhängigkeit vom Feldfokus bleibt erklärungsbedürftig |
| Durchmesser eingeben | 7 mm wurde im Feld sichtbar | Übernahme, tatsächliche Geometrieänderung und Undo wurden in dieser nativen Fahrt **nicht** abgeschlossen |

Danach war das Prüffenster minimiert; die Automatisierung meldete zusätzlich
Benutzereingabe und setzte die Interaktion nicht fort. Das ist weder ein
nachgewiesener Anwendungsabsturz noch eine erfolgreiche Endabnahme. Auch ein
früheres geschlossenes Prüffenster ohne gesicherten Prozessausgang wird nicht
als reproduzierbarer Produktfehler gezählt.

### 4.2 Direkt am Modell bearbeiten — Vorgabe vom 18.09.2026

Robert präzisiert nach der Durchsicht: Maße wie beim Bohrungsetzen direkt
am Modell anzeigen, das Eingabefeld etwas absetzen, daneben Haken zum
Bestätigen und Kreuz zum Abbrechen. Dasselbe bei Bewegen und weiteren
Operationen; Zahlenbearbeitung aus dem Panel herausnehmen. „Auf alle“ kann
unter dem Feld im Viewport stehen. **Das ersetzt den zuvor vorgeschlagenen
bloßen Umbau der Feldhierarchie im Merkmalpanel.**

**Am Code verifizierter Bestand:**

| Vorhandener Weg | Was bereits da ist | Was noch zusammengeführt werden muss |
|---|---|---|
| `PlacementFlow` in [placement_flow.py](../app/ui/placement_flow.py) | Kanten- und Mittenabstände, Bohrungstiefe als `LengthSpin` über der Ansicht; Maßlinien, kollisionsarme Feldplatzierung, Vorschau und Rückweg | Bestätigung steht in einer getrennten Platzierungsleiste; der Operationsdialog bleibt zusätzlich sichtbar |
| `FeaturePanel._settle_in_view` in [panels.py](../app/ui/panels.py) | „Im Bild einstellen“ öffnet vorhandene Maßlinien; eigener Signalweg zur Vorschau | Direkte Maße sind noch ein gesonderter Einstieg neben den vielen Panel-Eingaben |
| `TransformBar` in [transform_bar.py](../app/ui/transform_bar.py) | X/Y/Z-Versatz, Drehwinkel, Skalierung und Zielgröße; Enter übernimmt einmal | Seit Entscheidung vom 03.09. ausdrücklich kein Anwenden-Knopf; die neue Vorgabe ergänzt jetzt sichtbares ✓/× direkt am Feld |
| `DragValueBar` / `_apply_typed` in [viewport.py](../app/ui/viewport.py) | Zahlenfeld am Zug; Enter für Bewegung, Drehung, Skalierung, Fläche, Langloch und Skizzenhöhe | Freigabezeitpunkt hängt vom Weg ab: Körperzug kann beim Loslassen schreiben, Merkmalsvorschlag auf spätere Übernahme warten |
| Sammelbearbeitung `FeaturePanel._emit` | Gruppierte gleichartige Merkmale desselben Körpers, eine Transaktion | Schalter, Zielzahl und Vorschau an den gemeinsamen Entwurf im Viewport anbinden |

**Sollbild für eine gewählte Bohrung** — schematischer Entwurf, kein Screenshot:

```text
          Maßlinie am Durchmesser ──  Ø [ 6,00 mm ]  [✓] [×]
                                        □ Auf alle 4 gleichartigen Bohrungen anwenden

          Maßlinie zur Bezugskante ──   [12,00 mm]
```

Die aktive Handlung benennt den Bezug, etwa „Bohrung ändern“ oder
„Bohrung verschieben“. Durchmesser ist ein Zielmaß; Kantenabstand ist ein
Abstand zur hervorgehobenen Kante; X/Y/Z beim Bewegen sind Versatzwerte.
Diese Bedeutungen dürfen sich nicht beim Wechsel von Panel zu Viewport
ändern. Ein gerundeter Messwert bleibt als gemessen erkennbar; Normmaß und
Unsicherheit werden nicht erfunden.

**Ein Bedienvertrag für alle geeigneten Maßoperationen:**

1. Merkmal oder Körper wählen. Seine unmittelbar relevanten Maße erscheinen
   am Modell; ein Klick auf das Maß oder der passende Griff startet die
   Bearbeitung. Für den üblichen Maßwechsel ist kein vorgelagerter Dialog
   und kein „Im Bild einstellen“-Umweg erforderlich. Seltenere Handlungen
   bleiben über die gegliederte Kontextauswahl erreichbar.
2. Ein aktiver Operationsentwurf hält Ziel, Werte, Bezugssystem und
   Sammelauswahl. Tippen und Ziehen ändern denselben Entwurf und dieselbe
   Vorschau. Im Panel wird keine zweite unabhängig bearbeitbare Kopie
   derselben Werte geführt. Es bleiben höchstens seltene Zusatzoptionen und
   Erläuterungen, die nicht sinnvoll am Modell stehen.
3. Das Eingabefeld steht mit erkennbarem Abstand zur Maßlinie. Eine kurze
   Zuordnungslinie hält den Zusammenhang. Feld, Einheiten und ✓/× dürfen
   weder den Griff noch den betroffenen Rand verdecken; bei Platzmangel
   gemeinsam an einen freien Rand innerhalb des Viewports rücken. Die
   vorhandene Kollisionsbehandlung erweitern, kein zweites Layoutsystem.
4. **Ein Paar ✓/× je aktiver Operation**, am aktiven Feld beziehungsweise an
   der zusammengehörigen Feldgruppe. Bei X/Y/Z oder mehreren Abständen
   übernimmt ✓ alle Werte zusammen. Beim Fokuswechsel wandern nicht drei
   unabhängige Bestätigungen mit drei verschiedenen Zwischenständen mit.
5. **✓ oder Enter übernimmt genau einmal; × oder Escape verwirft den
   aktiven Entwurf.** Fokusverlust, Tab und Kamerabewegung übernehmen nichts.
   Wiederholtes Ziehen und Tippen bleibt bis zur Übernahme Vorschau; ein Undo
   nimmt anschließend die gesamte Handlung zurück. Nach ✓ ist der Entwurf
   verbraucht: ein weiterer Enter darf keinen zweiten Versatz auslösen.
6. Während der Vorschau bleibt „Noch nicht übernommen“ mit den beiden
   Schaltflächen sichtbar. Ein Klick außerhalb übernimmt nichts und lässt
   den Entwurf mit seinem bisherigen Ziel sichtbar. Eine andere Operation
   ersetzt ihn erst nach ✓/×; dafür kein zusätzlicher Bestätigungsdialog.
   Ungültige Werte bleiben korrigierbar, ✓ ist mit erklärtem Grund gesperrt,
   × bleibt verfügbar. Verspätete Rechenergebnisse dürfen den neueren
   Entwurf oder einen bereits verworfenen Zustand nicht zurückbringen.
7. **„Auf alle N gleichartigen … anwenden“ steht unmittelbar darunter**, nur
   wenn passende weitere Ziele existieren, anfänglich nicht aktiviert.
   Gemeint sind die für diese Handlung ermittelten Mitglieder desselben
   Körpers, nicht pauschal alle Löcher der Szene. Aktivieren zeigt alle
   betroffenen Stellen und eine gemeinsame Vorschau vor ✓. Wenn ein Ziel
   scheitert, keine stille Teilübernahme; der Entwurf erklärt das Hindernis
   und ermöglicht die Korrektur. Ein Undo nimmt alle Änderungen zurück.
8. Die Symbole tragen Tooltip und zugänglichen Namen („Bohrung ändern“,
   „Änderung verwerfen“), eindeutige Fokusmarke und ausreichende Trefferfläche.
   Bedeutung nicht nur über Grün/Rot. Tastaturfolge und Enter/Escape gelten
   am echten eingebetteten Editor, nicht nur bei direkt ausgelösten Signalen.

**Bewusste Verhaltensänderung:** Die bisherige Freigabe eines Körperzugs beim
Loslassen wird für diese Maßbearbeitungen durch den gemeinsamen Vorschau-
und Übernahmeweg ersetzt. Die frühere Entscheidung „kein Anwenden unten bei
Bewegen“ wird durch sichtbares ✓/× am aktiven Feld präzisiert. Ein zusätzlicher
Bestätigungsdialog entsteht nicht. Bei der Skizze bestätigt ein lokales
Maßfeld nur den Editorentwurf; es darf nicht jeden Tastendruck oder jedes Maß
als neue Geometrieoperation in den Dokumentverlauf schreiben.

**Übertragungsmatrix für den Ausbau:**

| Familie | Direktes Feld und Anker | Zusatz unmittelbar im Kontext |
|---|---|---|
| Bohrung setzen/ändern | Durchmesser an Quermaß, Tiefe entlang Achse, Abstände zur Fläche | Gleichartige Ziele, Durchgang/Sackloch soweit unterstützt |
| Verschieben | Versatz an Achse oder Abstand zur markierten Bezugskante | Zielumfang, Bezug eindeutig; ein ✓/× für zusammengehörige X/Y/Z |
| Drehen | Winkel am Drehbogen | Achse/Pivot, „aufs Bett“ bleibt ausdrücklich sichtbare Option |
| Skalieren | Zielmaß an Ausdehnung oder Faktor am Griff | Gleichförmig/achsweise; kein stiller Wechsel zwischen Faktor und Zielmaß |
| Verrundung/Fase | Radius beziehungsweise Abstand an gewählter Kante | Betroffene Kanten gemeinsam hervorheben |
| Hochziehen/Abtragen, Tasche, Wand | Höhe/Tiefe entlang Richtung, Wandmaß an Schnitt/Fläche | Richtung, Durchgang oder Öffnungsfläche nur nach tatsächlich verfügbarer Fachfunktion |
| Langloch/Torus/Gewinde | Fachlich benannte Länge, Breite, Radien, Steigung am passenden Maß | Nur sicher bestimmte und unterstützte Maße; keine erfundenen Normparameter |
| Muster/Verdoppeln | Abstand/Winkel am sichtbaren Muster, Anzahl daneben | Alle Instanzen in einer Vorschau und Transaktion |
| Bausteinmaße | Parameter am benannten Bausteinmerkmal | Änderung bleibt am Erzeugerschritt des Bausteins, keine versehentliche Einzelmerkmalsoperation |

Für Import/Export, Materialkatalog und andere Handlungen ohne räumliches Maß
wird kein künstliches Maßfeld erfunden. Die allgemeine Verfügbarkeit bleibt;
passende geometrische Bearbeitungen erhalten den direkten Weg. Netz und
B-Rep nutzen dasselbe Layout und denselben fachlichen Vertrag.

Abnahme zusätzlich zu §4.3: Panel geschlossen und trotzdem den Hauptweg
abschließen; Kantenabstand/Durchmesser/Zielmaß/Versatz korrekt unterscheiden;
Maus → Zahl → Tab → Zahl → ✓; Enter genau einmal; ×/Escape ohne Änderung;
Sammelvorschau und gemeinsames Undo; Fehler an einem Sammelziel; große Zahl,
Ausdruck und Anzeigeeinheit; Ränder, Zoom, kleines Fenster, HiDPI,
hell/dunkel und lange Übersetzungen. Maßlinien und Feldgruppe dürfen nie
unklickbar übereinanderliegen. Diese neue Vorgabe ist hier konzipiert,
**noch nicht implementiert oder nativ abgenommen**.

### 4.3 Kundenwege als Abnahme

Jede Zeile wird mit STL und STEP derselben Sollform gefahren, soweit die
Geometrie das jeweilige Format sinnvoll trägt. Zusätzlich ein selbst
erstelltes Projekt. Modellquelle darf keine andere fachliche Bedienung
erzwingen. Gemessen werden Erfolg ohne Hilfestellung, Fehlversuche,
Rückweg, Wartezeit und Maßtreue; Lernzeiten werden nicht erfunden.

| Ziel | Weg | Kritischer Nachweis |
|---|---|---|
| Loch vergrößern | Öffnen → Loch wählen → Durchmesser → Vorschau → Übernehmen | Nur gewünschtes Loch ändert sich; Undo/Redo; Maß bleibt nach Wiederöffnung |
| Loch verschieben | Loch wählen → Richtung/Versatz → Vorschau | Kein Materialrest; übrige Wand und Referenzen bleiben richtig |
| Halter selbst zeichnen | Skizze auf Fläche → Kontur/Maße → Hochziehen → Bohrung | Tastaturweg, offene Kontur erklären, Fläche und Projektion korrekt |
| Deckel anpassen | Außenform übernehmen → Abstand/Wand → Gegenstück | Tatsächlicher Freiraum und Passungsbezug, keine bloße Ø-Differenz |
| Rand abrunden | Kante wählen → Radius → Vorschau | Gleiche fachliche Aktion; unmöglichen Radius erklären, kleinerer Wert erneut möglich |
| Gewinde ändern | Importgewinde wählen → Maße/Gegenstück | Teilgewinde, Händigkeit und Steigung; kein Normprofil erraten |
| Grobe STL bearbeiten | Öffnen → Merkmal → Maß ändern | Näherung sichtbar, tatsächliche Formtreue geprüft, Original bleibt erreichbar |
| Früheres Maß ändern | Verlauf → Maß → Neuberechnen | Abhängige Skizzen/Passungen richtig oder konkret auflösbarer Konflikt |
| Fehler beheben | Fehlerstelle wählen → Vorschlag → erneut rechnen | Keine Sackgasse, gültige Eingaben erhalten, Undo funktioniert |
| Ergebnis weitergeben | Speichern → öffnen → STL/3MF/STEP passend exportieren | Einheiten, Körperzahl, Maße und zulässige Darstellung; kein falsches exaktes Versprechen |

Diese zehn Wege sind eine Abnahmespezifikation, keine Liste bereits nativ
bestandener Versuche. Für die Erstnutzerprüfung mindestens mehrere Personen
ohne CAD-Vorkenntnisse mit denselben Aufgaben beobachten; Stichprobe und
Ergebnisse offen ausweisen, keine allgemeine Marktführerschaft ableiten.

### 4.4 Sinnvolle Bezüge zum Ausrichten — Ergänzung vom 18.09.

Robert verlangt zusätzlich: Bei Abständen prüfen, ob sinnvolle Kanten und
Merkmale als Bezüge gefunden werden, damit man daran ausrichten kann.
**Nähe allein ist dafür kein ausreichendes Auswahlkriterium.**

Ist-Code in [scene/placement.py](../app/core/scene/placement.py):
`prepare_surface` vereint die Dreiecke einer zusammenhängenden Fläche,
`_straight_boundary` verbindet kollineare Randstücke. Bekannte Kreisränder
können anhand übergebener Merkmale ausgeschieden werden. `at_point` nimmt
anschließend die zwei nächsten nicht parallelen Randstücke; Außen- und
Innenränder gehen in dieselbe Kandidatenliste. Mittelpunktbezüge werden
bisher für Bohrungen mit senkrecht zur Fläche stehender Achse und
passender Tiefenlage gesammelt und nach Entfernung sortiert. `point_with_distances`
hält die gewählten Kanten beim numerischen Ändern fest. Das ist vorhandene
Grundlage, aber noch keine allgemeine Auswahl nach konstruktiver Bedeutung.

**Neue Gegenprobe mit echter Erkennung:** Box 20 × 20 × 4 mm minus koaxialer
Zylinder Ø0,5 mm, Höhe 10 mm, 48 Facetten; manifold-Differenz. Auf der
Oberseite `prepare_surface(mesh, top_face, detect(mesh))`, dann
`at_point(..., (0.3, 0.3, 2.0))`:

- `detect` liefert sechs Flächen, keine Bohrung.
- Es entstehen **52 Kantenkandidaten** statt nur der vier äußeren Kanten.
- Die zwei gewählten Referenzen sind Kreisfacetten mit je **0,032702 mm**
  Länge und angezeigtem Abstand **0,173891 mm**.
- `test_circle_facets_never_become_two_linear_measurement_references` besteht,
  weil die Testeingabe das Bohrungsmerkmal bereits ausdrücklich mitliefert.
  Das schützt den Fall mit erkannter Bohrung, nicht den hier gemessenen
  vollständigen Erkennungsweg.

Das ist ein Fehler der nutzbaren Referenzauswahl, kein Beweis, dass alle
Abstände falsch sind. Auch kleine echte gerade Ausschnittkanten müssen
weiter auswählbar sein: Der vorhandene 0,2-mm-Rechteckausschnitt ist dafür
bewusst die Gegenprobe. Pauschales Löschen kurzer Kanten wäre der falsche Fix.

**Vertrag für den direkten Maßeditor:**

1. Eine ausdrücklich gewählte Referenz hat Vorrang. Ohne solche Wahl werden
   fachlich geeignete Bezüge vorgeschlagen: gerade Außenkanten der aktuellen
   Fläche, echte Innenkanten, Bohrungs-/Zapfenmitten, Langlochachse oder
   belegte Symmetriemitte passend zur aktiven Handlung. Nicht jede Gruppe ist
   heute implementiert; die Ergänzung ist Teil des Ausbaus.
2. Triangulationsdiagonalen, Tessellierungsnähte und Facetten eines belegten
   gekrümmten Randes sind keine einzelnen Geradenbezüge. Fehlt eine sichere
   Klassifikation, den unsicheren Bezug kenntlich machen oder keinen
   automatischen Bezug wählen; keine Kreismitte oder Symmetrie erfinden.
   Die Entscheidung darf nicht allein davon abhängen, ob die globale
   Merkmalserkennung schon eine Bohrungs-ID vergeben hat.
3. Zuerst geometrische Eignung prüfen: dieselbe Trägerfläche beziehungsweise
   ausdrücklich gewählte Bezugsebene, richtige Materialseite, passender
   Achsenbezug und tatsächlich erreichbare Zielposition. Danach fachliche
   Bedeutung, numerische Stabilität und räumliche Nähe bewerten. Verdeckte
   Rückseiten oder andere Körper nicht allein wegen geringerem Bildabstand
   wählen. Andere Körper nur bei ausdrücklicher Auswahl und zulässigem Bezug.
4. Zwei Abstände müssen die Position unabhängig und stabil bestimmen. Fast
   parallele Referenzen über Kondition und fachliches Fehlerbudget ablehnen
   statt aus fast gleichem Winkel große Positionssprünge zu errechnen.
   Ein einzelner Abstand zur Bohrungsmitte bestimmt keine eindeutige
   Position; dafür zwei gerichtete Abstände oder Abstand plus Richtung.
5. Maßlinie und Bezeichnung sagen, **was** gemessen wird: senkrechter Abstand
   zur markierten Kante, gerichteter Versatz zur Achse, Mitte–Mitte oder
   tatsächlicher Randabstand. Ein Lochzentrum 10 mm von einer Außenkante
   entfernt bedeutet bei Ø6 mm nicht 10 mm Material zwischen Loch und Rand.
   Eine nötige Verlängerung einer Kante wird als Hilfslinie sichtbar.
6. Die vorgeschlagene Kante beziehungsweise das Merkmal wird mit markiert.
   Direkt an der Maßbeschriftung „Bezug ändern“ wählen und eine andere
   geeignete Kante/Mitte im Modell anklicken; kein Auswahl-Dialog. Bei
   gleichwertigen Kandidaten Alternativen sichtbar anbieten. Zentrieren,
   gleiche Abstände oder Achsen ausrichten nur als eindeutig bezeichnete
   passende Handlungen, nicht als unbemerkter Nebeneffekt einer Zahl.
7. Sobald die Eingabe oder ein Zug begonnen hat, bleiben Referenz, Vorzeichen
   und Bezugssystem bis ✓/× fest. Kamera, Zoom, eine etwas nähere Kante und
   Rundungsrauschen dürfen den Bezug nicht austauschen. Ein expliziter
   Bezugswechsel rechnet die Vorschau neu und zeigt den neuen Bezug.
8. Ein aus einem Bezug berechneter Versatz ist nicht automatisch eine
   dauerhafte Bindung. Wo nur Positionswerte gespeichert werden, darf die
   Oberfläche keine später mitwandernde Beziehung versprechen. Für einen
   gespeicherten assoziativen Bezug gelten Identität, Migration, Neuberechnung
   und Verwaisung aus Konzept §13.3; niemals eine flüchtige `edge_0`-Nummer
   aus der Kandidatenliste als dauerhafte Referenz speichern.

Abnahme auf Netz/B-Rep und derselben neu triangulierten Form: Platte mit
Bohrungen, abgerundete Außenkontur, konkaver Rand, winzige echte Innenkante,
unerkanntes kleines Kreisloch, geneigte Ebene, fast parallele Kanten,
Langloch und Zapfen, symmetrische Alternativen, verdeckte Rückseite und
benachbarter Körper. Auswählen → Bezug erkennen → Zahl ändern → Bezug
wechseln → ✓/× → Undo/Wiederöffnung. Maße und ausgewählte Referenzen gegen
unabhängige Sollgeometrie prüfen, nicht nur die Zahl angezeigter Felder.

Vier vorhandene gezielte Platzierungstests wurden nach dem Nachtrag gefahren:
Dreiecksdiagonale, bekannter Kreisrand, kleiner gerader Ausschnitt und
gekrümmte Fläche — **4 bestanden, 0,84 s, Exit 0**. Die oben beschriebene
Gegenprobe mit `detect(mesh)` bleibt ein zusätzlich nachgewiesener Fehler;
Anwendungscode wurde auch dafür nicht geändert.

## 5. Bibliotheken: konkrete Eignung statt Sammelliste

Primärquellen am 18.09.2026 geprüft. Keine neue Bibliothek installiert oder
als Abhängigkeit aufgenommen. Lizenzangaben sind technische Vorauswahl;
konkrete Dateien, transitive Abhängigkeiten, Hinweise und Auslieferung bleiben
vor einem Einbau gegen `licences.toml` zu prüfen.

| Kandidat | Was er hier beitragen kann | Grenze und Empfehlung |
|---|---|---|
| Vorhandenes OCP / OCCT 8.0.1 | B-Rep, STEP, Boolesche Operationen; `BRepTools_History` beschreibt erzeugte/geänderte/entfernte Teilformen | Zuerst vorhandene Fähigkeiten verwenden. Historie allein löst keine persistenten Namen über beliebige Neuberechnung. [History](https://occt3d.com/dev/doc/refman/html/class_b_rep_tools___history.html) |
| OCCT `ShapeUpgrade_UnifySameDomain` | Gleichartige benachbarte Flächen und Kanten zusammenführen | Hilft bei Nahtteilungen; keine allgemeine Rückgewinnung eines CAD-Modells aus STL. [Dokumentation](https://occt3d.com/dev/doc/refman/html/class_shape_upgrade___unify_same_domain.html) |
| Analysis Situs | Kanonische Erkennung/Umwandlung von NURBS in analytische Flächen; attributierter Nachbarschaftsgraph für zusammengesetzte Merkmale | Reserve für Restlücken nach Anschluss der vorhandenen OCCT-Erkennung (§5.2). BSD-3-Clause; konkrete Quellteile, OCP/OCCT-ABI, Python-Anschluss und Windows/Linux/macOS-Build ungeprüft. [Konvertierung](https://analysissitus.org/features/features_convert-canonical.html), [Lizenz](https://analysissitus.org/license.html) |
| NumPy / SciPy, vorhanden | Nichtlineare Fits und vorhandener Skizzenlöser; robuste Verlustfunktionen und Schranken sind verfügbar | Eigene Formverträge, Initialisierung, Ausreißer- und Konditionsprüfung nötig. Solverwechsel repariert keine falsche Messgröße. [least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) |
| trimesh / manifold, vorhanden | Netzaufbereitung und solide Boolesche Operationen | Kein fertiger semantischer CAD-Erkenner oder parametrischer Rückbau. Bestehende Basis beibehalten. [trimesh](https://github.com/mikedh/trimesh), [manifold](https://github.com/elalish/manifold) |
| Open3D 0.20.0, MIT | Punktwolken, Ebenensegmentierung und robuste planare Bereiche | Seit 16.09.2026 auch CPython-3.14-Wheels; Windows x64, Linux x64/ARM64, macOS ARM64 gelistet. Intel-macOS-Abdeckung nicht belegt. Plane-Patches ergeben keine Bohrungssemantik. Erst bei gemessenem Vorteil aufnehmen. [Paketdateien](https://pypi.org/project/open3d/0.20.0/), [Verfahren](https://www.open3d.org/docs/release/tutorial/geometry/pointcloud.html) |
| pyRANSAC-3D, Apache-2.0 | Kandidaten für geometrische Primitive | Nur Vergleichsbasis: der Zylinder-Code warnt selbst vor unzureichenden Ergebnissen an realen Daten (§5.3). Startwert, Genauigkeit und Ausreißerquote messen; kein Ersatz für Nachbarschaft, Innen/Außen und Zuordnung. [Repository](https://github.com/leomariga/pyRANSAC-3D) |
| planegcs 0.8.0, LGPL-2.1-or-later | Alternativer Skizzenlöser | Gelistete Wheels für CPython 3.12/3.13 auf Windows/Linux, keine unmittelbar passende 3.14-/macOS-Abdeckung belegt. Nur gegen konkrete fehlende Bedingungen und Korpus evaluieren. [Paket](https://pypi.org/project/planegcs/0.8.0/) |
| CGAL Shape Detection | RANSAC/Region-Growing für geometrische Primitive | Das betrachtete Paket steht unter GPL; durch Projektregel 15 ausgeschlossen. Eine andere Lizenz wäre eine gesonderte Entscheidung. [Paketlizenz](https://doc.cgal.org/latest/Shape_detection/group__PkgShapeDetectionRef.html) |
| libigl | Einzelne Netzalgorithmen | MPL-2.0-Kern und separat lizenzierte Copyleft-/CGAL-/TetGen-Bereiche unterscheiden. Hier kein belegter Bedarf für einen Einbau. [Lizenzgrenzen](https://libigl.github.io/license/) |
| `Sanaxen/mesh2cad` | OBJ-Segmentierung und Flächenanpassung bis IGES | MIT im Hauptprojekt reicht für die genannten CGAL-Abhängigkeiten nicht als Freigabe; alte OCCT-/CGAL-Basis, kein geprüfter Operationsnachbau. [Repository](https://github.com/Sanaxen/mesh2cad) |
| `Danxtream/Mesh2CAD-Converter` | Anderes Projekt mit STL→STEP und Ebenen-/Zylindererkennung | Nicht mit dem vorigen Repository vermischen. Geschlossenheit, Maßtreue, Lizenzkette und parametrische Historie hier nicht nachgewiesen; kein Einbau empfohlen. [Repository](https://github.com/Danxtream/Mesh2CAD-Converter) |
| Autodesk BRepNet | Forschung zu lernender Klassifikation von B-Rep-Teilformen | CC-BY-NC-SA-4.0 laut Repository; kein kommerziell freigegebener Produktbaustein und nach dem beschlossenen Umfang kein Geometrieverfahren. [Repository](https://github.com/AutodeskAILab/BRepNet) |

Analysis Situs beschreibt Bohrungserkennung über Flächen und Nachbarschaften,
auch wenn ein Lochrand nicht kreisförmig ist, etwa an einem Rohr. Das ist ein
passender Verfahrenshinweis für zusammengesetzte Solidon-Merkmale. Die
Graphindizes können sich bei Geometrieänderung ändern; der Graph ersetzt
deshalb nicht Solidons Referenzvertrag.
[Bohrungen](https://analysissitus.org/features/features_recognize-drill-holes.html),
[AAG](https://analysissitus.org/features/features_aag.html),
[Framework](https://analysissitus.org/features/features_feature-recognition-framework.html).

Wettbewerb als Funktionsreferenz, nicht als Leistungsbeweis: Fusion trennt
facettierte, prismatische und organische Netzkonvertierung; prismatische
Konvertierung nutzt Flächengruppen. Ein parametrischer Konvertierungsschritt
ist noch keine Rückgewinnung der ursprünglichen Konstruktionsgeschichte.
Shapr3D dokumentiert für Meshes Boolesche Operationen und Transformationen,
bei denen das Ergebnis Mesh bleibt. Daraus folgt weder ein genereller
Vorsprung von Solidon noch eine einfache Lösung unserer Paritätszusage.
[Fusion-Dokumentation](https://help.autodesk.com/view/fusion360/ENU/?guid=MESH-CONVERT-TO-SOLID),
[Shapr3D-Dokumentation](https://support.shapr3d.com/hc/en-us/articles/7874501863708-Mesh-files).

**Empfehlung:** bestehende Kerne behalten; Nachführung und Maßverträge
korrigieren und die bereits verfügbare kanonische Erkennung anschließen.
Gezielte Eigenentwicklung gehört ausdrücklich dazu (§§5.5–5.6).
Weitere Bibliotheken müssen eine danach verbleibende Lücke nachweislich
schließen. Ein Name oder Anbieterbenchmark begründet keinen Wechsel.

### 5.1 Vorhandener Versionssatz und konkrete Verbesserungsmöglichkeiten

Am 18.09. erneut gegen `constraints.txt`, installierte Paketmetadaten und
PyPIs JSON-API geprüft. Bei diesen elf Paketen stimmen installierte,
festgeschriebene und aktuell auf PyPI ausgewiesene Version überein:

| Bestandteil | Version | Folgerung für diese Untersuchung |
|---|---|---|
| [cadquery-ocp-novtk](https://pypi.org/project/cadquery-ocp-novtk/8.0.1.0.0/) | 8.0.1.0.0 | Vorhandene, bislang nicht angeschlossene Werkzeuge prüfen |
| [manifold3d](https://pypi.org/project/manifold3d/3.5.3/) | 3.5.3 | Netzboolesche Operationen behalten; `Mesh64` statt Genauigkeitsverlust durch float32 |
| [trimesh](https://pypi.org/project/trimesh/5.1.0/) | 5.1.0 | Geometrie- und Nachbarschaftsdaten je unverändertem Körper wiederverwenden |
| [NumPy](https://pypi.org/project/numpy/2.5.3/) / [SciPy](https://pypi.org/project/scipy/1.18.1/) | 2.5.3 / 1.18.1 | Eigene Residuen, Kandidatenfilter und Klassifikation auf vorhandener Numerik |
| [Shapely](https://pypi.org/project/shapely/2.1.2/) | 2.1.2 | 2D-Konturen und räumliche Vorauswahl auf einer definierten Ebene |
| [pygfx](https://pypi.org/project/pygfx/0.17.0/) / [wgpu](https://pypi.org/project/wgpu/0.32.0/) | 0.17.0 / 0.32.0 | Bestehende Modellansicht für Maßlinien und Trefferanzeige nutzen |
| [PySide6](https://pypi.org/project/PySide6/6.11.2/) | 6.11.2 | Echte Eingabefelder, Fokus, Tastatur und zugängliche ✓/×-Bedienelemente |
| [VTK](https://pypi.org/project/vtk/9.7.0/) | 9.7.0 | Bestehende kopflose Kollisions-/Bereichsprüfungen; kein Rendererwechsel |
| [Cython](https://pypi.org/project/Cython/3.3.0/) | 3.3.0 | Schon vorhandenes Bauwerkzeug als Option für gemessene Python-Schleifen |

Das ist kein vollständiger Sicherheits- oder Paketartefaktaudit. Insbesondere
beweist „aktuell“ weder Fehlerfreiheit noch Kompatibilität jedes künftigen
Updates. Lokal lief Python 3.14.2; `constraints.txt` nennt für Entwicklung/CI
3.14.7. Die ausgeführten Windows-Prüfungen sind deshalb kein Nachweis für den
identischen Interpreter der Paketbauten und keine plattformübergreifende
Auslieferungsabnahme.

Am Ist-Code geprüfte Optimierungsansätze, noch ohne behaupteten Zeitgewinn:

- [matching.py](../app/core/perceive/matching.py) erzeugt bereits blockweise
  vektorisierte Kosten, anschließend aber eine volle N×M-Matrix samt
  Rivalensuche. Eine konservative räumliche Vorauswahl mit vorhandenem
  SciPy und getrennte Zusammenhangskomponenten sind zu prüfen. Jede
  zulässige Zuordnung und jeder relevante Rivale muss erhalten bleiben;
  „nur nächster Punkt“ wäre fachlich falsch. Dichte Symmetrien bleiben der
  ungünstige Fall. [cKDTree](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html)
- [solver.py](../app/core/sketch/solver.py) nutzt bereits analytische dünn
  besetzte Ableitungen, TRF und LSMR. „Erst auf sparse umstellen“ wäre eine
  falsche Empfehlung. Bei verbleibenden Ausfällen zuerst Gleichungen,
  Skalierung, Rang, Startzustand und Konfliktdiagnose untersuchen. Robuste
  Fit-Verluste sind für verrauschte Messungen nützlich, dürfen aber keine
  verbindliche Skizzenbedingung still abschwächen.
- [enclosure.py](../app/core/geom/enclosure.py) und die Schichtanalyse nutzen
  bereits Shapely-STRtree. Dieser arbeitet mit zweidimensionalen Begrenzungen;
  Z wird nicht zum 3D-Abstand. Geeignet für projizierte Konturkandidaten,
  kein Ersatz für eine räumliche Kollisionsprüfung.
  [STRtree-Vertrag](https://shapely.readthedocs.io/en/stable/strtree.html)
- [brep/features.py](../app/core/brep/features.py) hat bereits
  Nachbarschaftslogik für Langlöcher. Diese gezielt um Konkavität,
  zusammengehörige Trägerflächen und Teilöffnungen erweitern; keinen zweiten
  unabhängigen Gesamtgraphen nur wegen einer Bibliotheksbezeichnung bauen.
- [brep/edit.py](../app/core/brep/edit.py) verwendet bereits
  `ShapeUpgrade_UnifySameDomain` und für das Wegnehmen von Verrundungen
  `BRepAlgoAPI_Defeaturing`. Weitere Anwendung auf zusammengesetzte Merkmale
  ist eine eigene Machbarkeitsprüfung; die APIs sind keine neu zu erfindenden
  Algorithmen. Auch ein erfolgreicher Eingriff muss Merkmale und Attribute
  nachführen.
- [overlay.py](../app/ui/overlay.py), [viewport.py](../app/ui/viewport.py) und
  [placement_flow.py](../app/ui/placement_flow.py) bilden die vorhandene
  Oberfläche. Maßeditor und Referenzvorschläge dort integrieren, auf eine
  Dokumentrevision beziehen und veraltete Vorschauergebnisse verwerfen.
  Der Wechsel zu einer anderen GUI oder einem anderen Renderer behebt
  weder unpassende Bezüge noch einen vergessenen Abschluss.

### 5.2 Kanonische Erkennung: vorhandenes OCCT tatsächlich ausprobiert

`ShapeAnalysis_CanonicalRecognition` ist in unserem installierten OCP
importierbar. Die API bietet Flächenerkennung für Ebene, Zylinder, Kegel und
Kugel, zusätzlich Kurvenprüfungen. In dieser Klasse gibt es kein `IsTorus`.
Fehlerstatus und gemeldete Abweichung müssen ausgewertet werden.
[OCCT-API](https://occt3d.com/dev/doc/refman/html/class_shape_analysis___canonical_recognition.html)

Ausgeführte Sonde auf dem NURBS-STEP-Körper aus §2.1: jede `TopoDS.Face` über
`TopExp_Explorer(..., TopAbs_FACE)` besuchen; pro Versuch einen frischen
Recognizer und ein `gp_Pln`, `gp_Cylinder`, `gp_Cone` beziehungsweise
`gp_Sphere` anlegen; `IsPlane`/`IsCylinder`/`IsCone`/`IsSphere` mit
**1e-6 mm ausschließlich als Sondentoleranz** aufrufen.

| Messgröße | Ergebnis |
|---|---|
| Solidon `features_of` am importierten NURBS-Körper | 0 Merkmale |
| Vorhandene OCCT-Analyse am identischen Körper | 6 Ebenen, 1 Zylinder |
| Zylinderdurchmesser, Soll 6 mm | 5,999999999999634 mm |
| Größtes vom Algorithmus gemeldetes `GetGap()` | 3,5270 × 10⁻¹³ mm |

Vier zusätzliche Kontrollen, jeweils nach `BRepBuilderAPI_NurbsConvert`
und mit derselben Sondentoleranz: Kugel R3 → eine Kugelfläche; Kegelstumpf
R4/R2, Höhe 10 → eine Kegelfläche und zwei Ebenen; Torus R15/r3 → eine
nicht klassifizierte Fläche; Zylinder R3/H10 nach X-Streckung 1,2 → zwei
Ebenen und eine nicht klassifizierte Mantelfläche. Der elliptische Mantel
wurde somit in dieser Probe nicht als Kreis-Zylinder fehlklassifiziert.
Diese vier Kontrollen liefen ohne zusätzliche STEP-Rundreise.

Das beweist eine nutzbare Kernfähigkeit für genau diesen Prüfkörper.
`GetGap()` ist hier keine unabhängig bestimmte globale Hausdorff-Schranke.
Für den Produktanschluss fehlen noch getrimmte Bereiche, Innen/Außen,
Teilwinkel, Nahtteilungen, Nachbarschaft und Referenzzuordnung. Insbesondere
ist der U-Parameter einer B-Spline-Fläche nicht automatisch der Winkel einer
analytischen Zylinderfläche. Den existierenden Analytikzweig nur mit einem
anderen Typetikett zu füttern wäre falsch. Weitere Kontrollen müssen
verformte Fast-Zylinder, Teilflächen und kleine Merkmale enthalten.

Eine zusätzliche ausgeführte Sonde schließt beim Torus einen weiteren
vorhandenen Weg nach: `BRep_Tool.Surface_s(face)` der NURBS-Fläche aus der
obigen Kontrolle an `GeomConvert_SurfToAnaSurf` übergeben und
`ConvertToAnalytical(1e-6)` aufrufen. Ergebnis ist `Geom_ToroidalSurface`,
Hauptradius 15,000000000000009 mm, Rohrradius 2,9999999999999987 mm;
gemeldeter `Gap()` 3,3995 × 10⁻¹⁴ mm. Die Klasse ohne `IsTorus` ist somit
keine Grenze des gesamten vorhandenen OCCT. Das ist eine Trägerflächenprobe,
keine Integration in einen gültigen neuen getrimmten Körper. Als reine
Erkennung darf der Kandidat die Eingabe nicht verändern; ein tatsächlicher
Ersatz der Körpergeometrie bleibt eine dokumentierte Op.
[Flächenkonvertierung](https://occt3d.com/dev/doc/refman/html/class_geom_convert___surf_to_ana_surf.html)

Davon unterscheiden: das separat angebotene
[Canonical Recognition Component](https://occt3d.com/components/canonical-recognition/)
mit weitergehend beschriebener Umwandlung und Topologiebehandlung. Dessen
Funktionsumfang und Vertriebsbedingungen dürfen nicht dem mitgelieferten
Open-Source-Kern zugerechnet werden; Kosten und Lizenzangebot wurden nicht
eingeholt. Zuerst den belegten vorhandenen Weg nutzen.

### 5.3 Ergänzungen und Alternativen: wann sie sich lohnen

| Option | Konkreter Nutzen | Empfehlung und Eintrittsbedingung |
|---|---|---|
| Analysis-Situs-Quellteile | Zusätzliche kanonische Umwandlung und AAG-Merkmalsanalyse | Nur einen nachgewiesenen Restfall ergänzen. Der untersuchte `asiAlgo_ConvertCanonical.h` trägt BSD-3-Clause, verwendet aber `ActAPI_IAlgorithm`; kein isolierter Ein-Datei-Baustein. `Perform` hat `buildHistory=false` als Vorgabe. Revision, vollständige Abhängigkeitskette und explizite Historie prüfen. [Header](https://analysissitus.org/refdoc/asi_algo___convert_canonical_8h_source.html) |
| pyRANSAC-3D | Kleine Vergleichsbasis für Primitive | Der geprüfte Zylinder-Code warnt selbst vor schlechten Ergebnissen mit realen Daten und zieht Stichproben über globales `random.sample`; der Seed eines Datengenerators steuert das nicht. Für nebenläufige reproduzierbare Ops braucht es einen lokalen Zufallsgenerator oder eine isolierte Ausführung. Eigene begrenzte Fits auf NumPy/SciPy zuerst vergleichen; keine Empfehlung als fertiger robuster Zylindererkenner. [Quellcode](https://github.com/leomariga/pyRANSAC-3D/blob/master/pyransac3d/cylinder.py) |
| PCL | RANSAC mit Normalen für Zylinder und weitere Punktwolkenverfahren | BSD-Lizenz im Hauptprojekt; C++-Integration und transitive Pakete zusätzlich prüfen. Interessant bei einem konkret belegten Segmentierungsdefizit; kein direkt bewiesener Python-3.14-Paketweg und kein Grund, vorhandene STL-Topologie zuerst zu verwerfen. [Verfahren](https://pointclouds.org/documentation/tutorials/cylinder_segmentation.html), [Lizenz](https://github.com/PointCloudLibrary/pcl/blob/master/LICENSE.txt) |
| Polylidar3D | Planare Segmente und konkave Polygone mit Innenrändern aus Netzen/Punkten | MIT; C++ mit Python-Anbindung. Vergleich für langsame Konturextraktion, kein Rundungs-/Gewindeerkenner. Projekt nennt Windows/Linux; aktueller CPython-3.14-/macOS-Bau nicht nachgewiesen. [Projekt](https://github.com/JeremyBYU/polylidar), [Lizenz](https://github.com/JeremyBYU/polylidar/blob/master/LICENSE) |
| MeshLib | Umfangreiche native Reparatur-, Abstand-, Offset- und Netzwerkzeuge | Keine frei kommerziell nutzbare Alternative im geprüften Stand: eigene Non-Commercial-/Education-Lizenz, kommerzielle Nutzung gesondert. Erst bei ungelöster fachlicher Lücke und geklärtem Vertrag evaluieren; Anbieterbenchmarks sind kein Solidon-Nachweis. [Lizenz](https://github.com/MeshInspector/MeshLib/blob/master/LICENSE) |
| CadQuery/build123d | Höhere Modellierabstraktionen über OCCT | Kein anderer Rechenkern und kein fertiger STL-Merkmalserkenner. Die vorhandene Op-/Parameterstruktur müsste zusätzlich abgebildet werden; derzeit kein belegter Vorteil für einen Austausch. [build123d](https://github.com/gumyr/build123d) |
| `spookylukey/planegcs` | Python-Anbindung an FreeCADs Skizzenlöser | Konkreter Kandidat für einen Solververgleich; nicht mit gleichnamigen WASM-/TypeScript-Projekten vermischen. 0.8.0 hat nur die oben genannten Wheels. Eigenbau ist möglich zu untersuchen, nicht als erledigt anzunehmen. [Projekt](https://github.com/spookylukey/planegcs), [Release](https://pypi.org/project/planegcs/0.8.0/) |
| CoACD statt V-HACD | Alternative konvexe Zerlegung für Vorschläge im Auto Split | **Im Projekt bereits geprüft und verworfen**, Bauplan §36 und historischer Auto-Split-Vergleich im ROADMAP-ARCHIV: V-HACD lieferte die bessere Einschnürungsstelle; genaues CoACD war langsamer, grobe Einstellung lieferte keinen brauchbaren Schnitt. V-HACD bezeichnet sich upstream als eingestellt und verweist auf das MIT-lizenzierte CoACD; das hebt den lokalen Befund nicht auf. Erneute Prüfung nur bei konkretem Anlass und neuen Korpusmesswerten, kein beschlossener Wechsel. [V-HACD-Status](https://github.com/kmammou/v-hacd), [CoACD](https://github.com/SarahWeiii/CoACD), [Lizenz](https://github.com/SarahWeiii/CoACD/blob/main/LICENSE) |

Bei punktwolkenbasierten Verfahren bleiben Dreieckszuordnung und Herkunft
erhalten. Ein erfolgreicher Zylinderfit entscheidet weder „Bohrung oder
Zapfen“ noch ob das Material gefahrlos entfernt werden darf. Große Pakete
werden nicht wegen einzelner API-Namen eingebaut. Vor jeder Aufnahme zählen
Verbesserung am eigenen Korpus, benötigte Binärgrößen, kalter Start,
Speicherbedarf, Wartung und dieselben Kundenwege auf allen Zielplattformen.

Auch die verbleibenden vorhandenen Geometriehilfen haben klar begrenzte Rollen:
[autosplit.py](../app/core/geom/autosplit.py) ruft
`mesh.raw.convex_decomposition(...)` zur Vorschlagsbildung auf; die
konvexen Hüllen sind kein maßhaltiger Ersatz des Originalteils.
`fast-simplification` arbeitet bereits hinter trimeshs Dezimierung, mit
ausgewiesenem manifold-Rückfall in
[mesh_ops.py](../app/core/geom/mesh_ops.py). Das Projekt beschreibt zudem
die Wiederholung von Kantenkollapsen und eine Vertexzuordnung: möglicher
Vergleich für Attributübertragung, jedoch kein automatischer Erhalt
konstruktiver Merkmale oder eine Formfehlerschranke.
[Dokumentation](https://github.com/pyvista/fast-simplification)

`scikit-image` trägt Marching Cubes hinter Voxelwegen, unter anderem in
[boolean.py](../app/core/geom/boolean.py),
[hollow.py](../app/core/geom/hollow.py) und
[lattice.py](../app/core/geom/lattice.py). Verbesserungsziel ist zuerst ein
nachvollziehbares Auflösungs-/Abweichungsbudget einschließlich dünner Wände
und kleiner Bohrungen. Die Extraktion einer Rasterfläche stellt verlorene
Details nicht wieder her. Ein neuer Mesher wäre nur bei belegter Verbesserung
derselben Fälle gerechtfertigt.
[Marching-Cubes-API](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.marching_cubes)

### 5.4 Reihenfolge der geometrischen Verbesserung

1. Erzeugerwissen und echte analytische B-Rep-Flächen verwenden; Herkunft und
   Maßvertrag erhalten. Nach Transformationen Geometrie und Merkmale gemeinsam
   aktualisieren, bevor eine aufwendigere Erkennung hinzukommt.
2. Analytische Träger in NURBS mit dem vorhandenen OCCT prüfen. Am Netz
   Topologie und Normalen zu Kandidaten zusammenfassen, dann geometrisch
   passende Kontur-/Flächenfits durchführen. Eine Punktwolkenmethode ist
   gegebenenfalls eine Ergänzung für schwierige Bereiche.
3. Kandidaten anhand unabhängiger Restfehler, Abdeckung, Kondition,
   Nachbarflächen und Innen/Außen klassifizieren. Geometrische Näherung,
   angenommener Konstruktionsradius und tatsächliche Kollisionsfreiheit sind
   getrennte Aussagen. Ein regelmäßiges Polygon kann absichtlich so gebaut
   worden sein; seine ursprüngliche Entwurfsabsicht steht nicht in der STL.
4. Zusammengesetzte Merkmale aus einem gemeinsamen Graphen bilden und
   überlappende Deutungen ausdrücklich behandeln. Kleine Merkmale lokal
   prüfen, nicht pauschal nach einer globalen Größenquote verlieren.
5. Dieselben fachlichen Merkmalsdaten an Auswahl, Maße, Ausrichtung, Agent
   und Operationen geben. Nur geometrisch gültige Handlungen anbieten;
   Mehrdeutigkeit im Modell erklären. Nachbau erst hinter diesem Vertrag.

### 5.5 Was wir sinnvoll selbst schreiben können

**Eigenentwicklung ist ein gleichberechtigter Lösungsweg.** Die sinnvolle
Grenze verläuft zwischen klar definierter Solidon-Funktion und neuer
Grundlagentechnik, nicht zwischen Python und C++. KI kann Entwurf, Code,
Bindungen, Gegenbeispiele und Tests liefern; korrekt wird das Ergebnis durch
unabhängige Prüfung. Lizenzpflichten fremder Vorlagen bleiben bestehen.

| Aufgabe | Bevorzugter Weg | Begründung / unabhängiger Nachweis |
|---|---|---|
| Maßeditor, ✓/×, Referenzvorschlag, Zielumfang | Eigener Python-/PySide-Code auf bestehenden Abläufen | Das ist Solidons Bedienvertrag. Reale Maus-/Tastaturfolge, Fokus, Zoom, Verdeckung, Undo und Wiederöffnung prüfen |
| Bohrung/Senkung/Langloch/Torus/Gewinde als fachliches Merkmal | Eigene Klassifikation über vorhandener Kerngeometrie und Nachbarschaft | Kein Kandidat liefert unsere vollständige Semantik. Innen/Außen, Teilformen, Überschneidungen und absichtliche Polygone als Gegenfälle |
| Kreis-/Zylinder-/Kegel-/Torusfits | Eigene Residuen und Modellwahl, NumPy/SciPy als Rechenbasis | Teilabdeckung, ungleichmäßige Unterteilung und tatsächliche Kontur korrekt behandeln. Robuste Verlustfunktion allein genügt nicht; Sollradien und verformte Negativkörper prüfen |
| Referenzerhalt und Zuordnung | Eigene Regeln mit Kernhistorie, Erzeugerherkunft und geometrischen Kandidaten | Verschieben/Skalieren/Kantenaufteilung, Symmetrie und Wiederöffnung prüfen; Koordinatenhash oder Bibliotheksindex ist keine dauerhafte Identität |
| Langsame Schleifen über Netznachbarschaft, Konturen oder Residuen | Erst Python/NumPy-Referenz, dann bei belegtem Engpass Cython oder C++ | Gesamten Kundenweg inklusive Kopien messen; Ergebnis, Abbruch und Speichergrenze gegen Referenz erhalten |
| Importgewinde ohne Erzeugerwissen | Begrenzte eigene geometrische Analyse auf OCCT-/Netzdaten | Querschnitte und Flankenperiodik als Hypothesen prüfen; Händigkeit, Gangzahl, Teilgewinde und beliebige Parametrisierung sind besonders riskant. Noch kein fertiger Algorithmus belegt |
| Vollständiger B-Rep-Kern, allgemeine robuste Boolesche Operationen, universeller NURBS-Schnitt | Vorhandenes OCCT/manifold verwenden | Ein Neubau vervielfacht Numerik-, Topologie- und Wartungsrisiken; die belegten Solidon-Lücken begründen ihn nicht |

Für mathematische Eigenentwicklung zählen analytische Sollkörper und
bewusst fehlschlagende Fälle vor dem Produktanschluss. Eine zweite Fassung
desselben KI-Algorithmus ist keine unabhängige Referenz. Geeignet sind
geschlossene Sollformeln, bekannte Konstruktionsparameter, metamorphe
Prüfungen (Lagewechsel, Maßstab, Neuvernetzung) und unabhängige Kernabfragen.
Auch diese Nachweise decken jeweils nur ihren angegebenen Bereich ab.

### 5.6 C++, Cython oder andere Sprache: konkrete Anschlussgrenze

**Vorschlag:** Python bleibt für Ablauf, Dokumentzustand und fachliche Regeln
zuständig. Ein nativer Baustein übernimmt eine abgegrenzte Berechnung, wenn
ein fehlendes Verfahren oder ein gemessener Engpass das rechtfertigt.

- **Cython zuerst mitvergleichen**, wenn wenige vorhandene Python-Schleifen
  dominieren. Es ist bereits Bauabhängigkeit; typisierte Memoryviews können
  numerische Arrays verarbeiten. Ein kompilierter Bau allein beschleunigt
  jedoch keine bereits in OCCT/NumPy ausgeführte Rechnung.
  [Memoryviews](https://cython.readthedocs.io/en/latest/src/userguide/memoryviews.html)
- **C++** ist passend für neue topologische Algorithmen, viele kleine
  Geometrieabfragen oder einen gezielten Anschluss an C++-Bibliotheken.
  `pybind11` (BSD-3-Clause) und `nanobind` (BSD-3-Clause) sind Kandidaten für
  die Anbindung. pybind11 dokumentiert Python-3.14-Unterstützung;
  tatsächliche OCP-Typübergabe, Laufzeiten und Paketbauten müssen dennoch
  erprobt werden. Beide wären neue Bauabhängigkeiten und brauchen feste
  Versionen sowie Lizenzbeilage.
  [pybind11](https://pybind11.readthedocs.io/en/stable/changelog.html),
  [Lizenz](https://github.com/pybind/pybind11/blob/master/LICENSE),
  [nanobind-Lizenz](https://github.com/wjakob/nanobind/blob/master/LICENSE)
- **Rust oder eine andere Sprache** ist nicht ausgeschlossen. Für die
  jetzigen Lücken ist ein zusätzlicher Werkzeug-/Binding-Satz aber noch
  nicht gerechtfertigt; C++ liegt beim Anschluss an OCCT näher, Cython beim
  Beschleunigen vorhandener Python-Rechnung. Eine Sprachenpräferenz ersetzt
  den gemessenen Vergleich nicht.

Für einen ersten nativen Prototyp genügt eine schmale Schnittstelle:
Koordinaten als float64-Arrays, Indizes mit geprüften Grenzen, explizite
Einheit und Toleranz, optional gespeicherter Startwert; zurück kommen
Kandidaten, Restfehler, Abdeckungen und deren Eingabezuordnung. Der Baustein
ändert keinen Dokumentzustand. Keine Python-/Qt-Callbacks unter freigegebenem
GIL, keine rohen Pointer aus Projektdateien und keine globalen Zufallszustände.
Eigentum, Lebensdauer, zulässige Strides und notwendige Kopien sind Teil des
Vertrags. Ein Python-Thread kann einen nativen Aufruf nicht beliebig beenden:
lange Verfahren brauchen kooperativen Abbruch oder einen ausdrücklich
isolierten Arbeiterprozess. Fortschritt/Abbruch werden über `OpContext`
weitergegeben. Free-Threading wird dafür nicht vorausgesetzt.

Ein Modul, das `TopoDS_Shape` direkt annimmt, muss dieselben OCCT-Bibliotheken,
ABI und kompatible Typbindungen wie unser OCP verwenden. Das wird zuerst an
Erzeugen → übergeben → ändern → freigeben geprüft. Ein zweiter mitgebündelter
OCCT-Kern oder ungeprüfte Pointer-Casts sind kein tragfähiger Anschluss.
Arraybasierte Verfahren vermeiden diese Kopplung und sind für den ersten
Beschleunigungsprototyp einfacher unabhängig zu prüfen.

Vor Aufnahme: Python-Referenz und native Fassung gegen denselben Korpus,
kleine Fälle und große/problematische Netze; Ende-zu-Ende-Zeit einschließlich
Konvertierung, Spitzenbedarf, Abbruchlatenz und Wiederholbarkeit messen.
Zusätzlich Speicher-/Grenzprüfungen im nativen Testbau, Fehlerübersetzung,
Installation im sauberen Paket und CI für alle unterstützten Zielplattformen.
Keine ungemessene Beschleunigungszahl, keine reduzierten Geometrieprüfungen
und kein anders arbeitender stiller Rückfall. Solange ein Vorteil oder die
Auslieferung nicht belegt ist, bleibt der bestehende Weg maßgebend.

## 6. Zusätzlicher Ausbau — inzwischen vollständig beauftragt

Im untersuchten Operations-/Skizzenschema fehlen unter anderem variable
Verrundungen, Fasen mit getrenntem Abstand/Winkel, frei gewählte Öffnungsflächen
beim exakten Aushöhlen, ausgewählte Entformungsflächen und weitere Varianten
von Schnitt durch Drehen/Führen/Überblenden. Auch zusätzliche Skizzenkurven
und Bedingungen sowie Einfügen/Umsortieren/Unterdrücken von Verlaufsschritten
sind eigenständige Ausbaubereiche. Bestehende Körpermuster sind nicht dasselbe
wie ein Muster ausgewählter konstruktiver Merkmale.

Diese Gebiete waren zunächst Vorschläge. Auf die ausdrückliche Nachfrage
nach ihrer Aufnahme antwortete Robert am 18.09. **„alles“**. Sie sind damit
verbindlicher Zusatzumfang. Fachliche Quelle ist
[Konzept §14.2](konzept-vollwertiges-cad-2026-09.md#142-voller-ausbau-entscheidung-vom-18092026);
die Umsetzung samt zusätzlichen Kundenwegen steht in §§13.2/13.9.

| Vollständig aufgenommenes Gebiet | Lieferpakete im Konzept |
|---|---|
| Variable Verrundung, Fasen mit getrennten Abständen oder Abstand/Winkel | P6.1/P6.2 |
| Frei gewählte Öffnungs- und Entformungsflächen | P6.3/P6.4 |
| Schnitt durch Drehen, Führen und Überblenden | P6.5a/P6.5b/P6.5c |
| Zusätzliche Skizzenkurven und Bedingungen, im Plan konkretisiert | P6.6a/P6.6b |
| Lineare, kreisförmige und gespiegelte Merkmalsmuster | P6.7 |
| Einfügen, Umsortieren und Unterdrücken/Reaktivieren im Verlauf | P7.1/P7.2/P7.3 |
| STEP-Mehrkörperimport mit Namen, Farben und Instanzlagen | P7.4 |

Die zehn bisherigen Kundenwege bleiben Pflicht; zusätzliche End-zu-Ende-
Wege kommen dazu. Gemeinsame Maßbedienung und Netz-/B-Rep-Parität gelten auch
für den Ausbau. Bibliotheken und Eigenentwicklungen sind in Konzept §13.8
den Paketen zugeordnet. Das beauftragt keine pauschale Installation aller
Alternativen. `offset_face` und die übrigen ausdrücklichen Nicht-Ziele
bleiben entsprechend Konzept §15 ausgeschlossen.

STEP-Mehrkörperimport und Erhalt von Namen/Farben sind vom Konstruieren einer
Baugruppe zu unterscheiden. Der heutige STEP-Leser übernimmt `OneShape()`;
eine vollständige XCAF-Strukturübernahme ist damit nicht belegt. P7.4
schließt diese Importlücke in der flachen Szene. Ein Baugruppenbaum und
Baugruppenbedingungen bleiben außerhalb des Auftrags.

## 7. Belastbare Abnahme statt Prozentzahl aus einer Stichprobe

Eine gemeinsame Matrix muss **Darstellung × Merkmal × Handlung × Zustand**
erfassen. Ausgangsbestand 132 Ops/35 Bausteine/12 Merkmalsarten; nicht jedes
kartesische Paar ist sinnvoll. Jede Kombination erhält „bestanden“,
„fachlich nicht anwendbar mit Grund“ oder „offen/fehlerhaft“. Ein fehlender
Test oder ein ausgegrauter Befehl zählt nicht als Parität.

Korpusachsen:

- Analytischer B-Rep, analytische Form als NURBS, STEP-Rundreise, feines und
  grobes STL, neu triangulierte identische Form, offene oder beschädigte
  Eingabe. Reparierte Daten getrennt vom Original werten.
- Alle zwölf Arten, jeweils innen/außen beziehungsweise vollständig/teilweise,
  schräg, gespiegelt und an einer Grenze; zusammengesetzte und sich
  überschneidende Merkmale; bewusst polygonale Negativbeispiele.
- Größenreihe, ungleichmäßige Dreiecksgrößen, lokale Ausreißer und Rauschen;
  feste gespeicherte Startwerte. Kleine Funktionsmerkmale auf großen Körpern
  dürfen nicht an einer globalen Volumenquote verschwinden.
- Nach Maßänderung, Verschieben, Drehen, Skalieren, Boolescher Operation,
  Qualitätswechsel, Cachetreffer, Undo/Redo sowie Speichern/Wiederöffnen.
- Windows, Linux und macOS für die gemeinsam ausgelieferten Pfade;
  Erkennungsqualität und geometrische Abweichung getrennt von identischen
  Fingerabdrücken prüfen. RM-186/RM-187 bleiben eigenständige Nachweise.

Kennzahlen je Familie: übersehene und fälschlich erkannte Merkmale,
Maß-/Achsenfehler, Referenzerhalt, tatsächliche lokale Formabweichung,
Topologie, Laufzeit und Spitzenbedarf. Schwellen kommen aus fachlichem
Genauigkeitsbudget und Bauplan §31, nicht aus nachträglicher Anpassung an den
schlechtesten Lauf. Bei Formabstand klar benennen, ob nur diskrete Stichproben
gemessen oder eine gesicherte Schranke nachgewiesen wurde.

Ein Nachbau darf nicht nur Volumen und Bounding-Box treffen. Versetzte
Bohrungen, verlorene dünne Rippen, verschlossene Kanäle und geänderte
Komponentenzahl sind Gegenbeispiele. Die Originaldatei, der geprüfte Kandidat
und die akzeptierte Abweichung müssen nachvollziehbar bleiben.

## 8. Tatsächlich ausgeführte zusätzliche Tests

Zusätzlich zu Konzept §17, jeweils Exit 0:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_geometry_review_regressions.py tests/test_sketch_end_to_end.py tests/test_recognition_regressions.py tests/test_digest_and_fits.py
# 356 bestanden, 7,91 s

.venv/Scripts/python.exe -m pytest -q tests/test_feature_panel.py tests/test_local_recognition_flow.py tests/test_interface_limits.py tests/test_sketch_editor.py tests/test_operation_ui.py
# 551 bestanden, 230,86 s
```

**907 zusätzliche bestandene Testfälle**, keine übersprungenen in diesen
beiden Läufen. Die im Konzept zuvor genannten 190 bestandenen/141
übersprungenen Fälle werden nicht zu einer behaupteten einzigartigen
Abdeckungszahl addiert: gezielte frühere Läufe können sich überschneiden.
Die numerischen Sonden und die begrenzte native Fahrt stehen separat oben.

In diesen gezielten Läufen noch kein vollständiger Torlauf. Die vorhandene
OCCT-API wurde anschließend nach §5.2 erprobt; keine externe Bibliothek
installiert, keine C++-Erweiterung gebaut, keine gefundenen Produktfehler
implementiert. Vollständige native Endabnahme und Erstnutzerprüfung bleiben
offen. Die Gegenbeispiele zeigen gerade, welche Verträge die bisher grünen
Tests noch nicht ausreichend absichern.


Abschließender, vom Projektwerkzeug zugeordneter Dokumentlauf:

```powershell
.venv/Scripts/python.exe tools/affected_tests.py konzepte/konzept-vollwertiges-cad-2026-09.md konzepte/recherche-cad-paritaet-2026-09.md konzepte/README.md ROADMAP.md --run
```

**2397 bestanden, 149 übersprungen, 39 abgewählt; Werkzeug und sämtliche
Teilprozesse Exit 0.** Darin 581 Hauptfenster- und 70 Lebensdauerprüfungen;
Fensterdateien wurden durch das Werkzeug getrennt gefahren. Abgewählte
Leistungstests und übersprungene Fälle zählen nicht als Abnahme. Dieser Lauf
überschneidet sich mit den gezielten Läufen und wird nicht als zusätzliche
unabhängige Funktionsabdeckung addiert. Nach den Bediennachträgen außerdem
Dokumentverweise, Codeblöcke, Roadmap-Anker, unveränderte 16 ursprüngliche
Entscheidungszeilen und `git diff --check` geprüft.

**Abschluss vor Commit, 18.09.:** Ruff-Prüfung und Formatprüfung bestanden
(ein zunächst unformatiertes Beispiel wurde korrigiert und nachgeprüft),
mypy ohne Befund in 297 Quelldateien. Nach der Bibliotheksvertiefung bestanden
die 15 Roadmap-/Dokukartenprüfungen; lokale Dateiverweise, Codeblöcke und
die ursprünglichen 16 Entscheidungen wurden erneut geprüft.
Der begonnene vollständige Torlauf wurde auf Roberts ausdrückliche Anweisung
abgebrochen; die eigene Prozesskette wurde beendet. Die separaten
Leistungstests wurden nicht gestartet. **Kein vollständig grünes Tor
behauptet.** Die bereits oben protokollierten abgeschlossenen Läufe bleiben
Teilnachweise; Implementierung und vollständige Produktabnahme bleiben offen.
