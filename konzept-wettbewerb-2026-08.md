# Konzept — Solidon3D gegen das Wettbewerbsfeld (11.08.2026)

Ein Durchgang durch **alle** Bereiche der Anwendung, jeder gegen die Programme
gehalten, die denselben Bereich bedienen. Anlass ist keine einzelne Fundstelle,
sondern die Frage vor der Veröffentlichung: *Wofür soll jemand 49 Euro zahlen,
wenn Fusion, Orca, Blender und FreeCAD nichts kosten?*

**Verhältnis zu den bestehenden Konzepten.** `konzept-sindricad.md` misst gegen
**einen** Konkurrenten und hat vier Bausteine beschlossen; dieses Dokument zieht
das Feld auf und prüft, was von jenen Befunden heute noch offen ist.
`konzept-bedienung.md` ist die Durchsicht der eigenen Oberfläche — die neun
Skizzenpunkte stehen dort und werden hier **nicht** wiederholt (Doku-Doktrin,
Regel 3). Was hier neu ist, ist die Breite: Generieren, Agent, Analyse,
Plattform, Sprache, Sichtbarkeit, Preis.

**Methode.** Der Ist-Stand ist gemessen, nicht erinnert: Register, Bausteine,
Formate, Backends und Profile aus dem laufenden Code ausgelesen. Der Marktstand
kommt aus Recherche vom 11.08.2026; Preise sind Anhaltspunkte, keine Zusagen.

---

## Teil 1 — Das Feld in sechs Gruppen

Solidon steht nicht in einem Markt, sondern in sechs. Das ist die erste
Erkenntnis dieses Durchgangs: Es gibt kein Programm, das dasselbe tut, aber es
gibt in **jedem einzelnen Bereich** jemanden, der darin besser ist als wir.

| Gruppe | Vertreter | Preis | Ihre Stärke |
|---|---|---|---|
| **G1 Parametrisches CAD** | Fusion 360, SolidWorks for Makers, Onshape, FreeCAD 1.x, SindriCAD, Alibre | 0 € (Personal) bis ~545 $/J | Historie aus Features, Baugruppen, Zeichnungen |
| **G2 Direktmodellierer** | Plasticity (~150 $ einmalig), Shapr3D (~299 $/J), Blender, ZBrush | 0 bis 299 $/J | Freiform, Geschwindigkeit, Gefühl |
| **G3 Einsteiger und Anpasser** | Tinkercad, SelfCAD, Womp, **MakerWorld Parametric Model Maker**, Thingiverse Customizer | 0 € | Null Einstiegshürde, direkt am Modellkatalog |
| **G4 Mesh und Reparatur** | Meshmixer (eingestellt), 3D Builder (abgekündigt), MeshLab, Netfabb, Magics, Blender-Toolkit | 0 € bis vierstellig | Reparatur, Dezimierung, Analyse |
| **G5 Slicer** | OrcaSlicer 2.9.4 / 3.0, PrusaSlicer, Bambu Studio, Cura, ElegooSlicer | 0 € | Kalibriersuite, organische Stützen, Maschinenwissen, Netzwerkdruck |
| **G6 KI** | Zoo, AdamCAD, Spectral SGS-1 (Text→CAD); Meshy, Tripo, Hunyuan3D, Modly (Text→Mesh); Autodesk Assistant (Copilot); Blender-MCP, FreeCAD-MCP (Agenten) | 0 € bis Abo | Neuheit, Aufmerksamkeit, Kapital |

Drei Bewegungen im Feld, die uns unmittelbar betreffen:

1. **Autodesk baut generative, editierbare B-Rep-Geometrie in Fusion** — aus
   einem Prompt ein änderbares CAD-Ergebnis, angetrieben von eigenen
   Foundation-Modellen. Das ist Säule A, von der stärksten Adresse im Markt.
2. **Bambu hat den Anpassungsfall an den Katalog geholt.** Der Parametric Model
   Maker läuft direkt auf der Modellseite von MakerWorld, seit v1.0 auch mit
   Fusion-Dateien. Wer ein Teil anpassen will, verlässt die Seite nicht mehr.
3. **Der Agentenzugang ist zum Standard geworden, nicht zum Merkmal.** Blender-
   MCP zählt 17.800 Sterne, FreeCAD-MCP bringt 165 Werkzeuge über 15 Module.
   „Man kann es fernsteuern" verkauft nichts mehr; *wie sauber* es fernsteuerbar
   ist, könnte.

---

## Teil 2 — Der Bereichsdurchgang

Je Bereich: was Solidon heute misst, wer es besser kann, das Urteil, die
Empfehlung. Das Urteil ist eine von drei Marken — **führend**, **gleichauf**,
**zurück**.

### 2.1 Konstruieren, parametrisch (Säule A)

**Stand:** 77 Operationen im Register (16 davon aus der Bausteinbibliothek), Projektparameter mit
eigener Grammatik ohne `eval`, Passungen in vier Arten, Op-Stack
non-destruktiv, Undo auf Transaktionsebene.

**Wer es besser kann:** Fusion und SolidWorks haben eine echte Feature-Historie
mit Referenzen auf Modellkanten, Baugruppen, Gelenke und Zeichnungsableitung.
Wir haben einen linearen Stapel ohne Verzweigungen (§15.4) und keine
Baugruppenverwaltung — beides ausdrücklich so gewollt und im README benannt.

**Urteil: gleichauf für 3D-Druck-Teile, zurück für Maschinenbau.** Der
Unterschied ist kein Mangel, solange die Zielgruppe stimmt. Für ein Gehäuse mit
Heat-Sets und Schnappverbindung ist unser Weg kürzer als Fusion. Für eine
Baugruppe aus zwölf Teilen mit Gelenken ist er nicht vorhanden.

**Empfehlung:** Nichts bauen. Die Abgrenzung im README ist gut — sie gehört
zusätzlich auf die Website, denn dort steht heute nur, was wir können.

### 2.2 Skizze und exakter Kern

**Stand:** Eigener 2D-Solver mit **neun** Zwangsbedingungen (`distance`,
`coincident`, `horizontal`, `vertical`, `parallel`, `perpendicular`, `tangent`,
`symmetric`, `fixed`) plus `reference`, fünf Elementarten inklusive Spline.
Ändern-Gruppe ist inzwischen da: `trim`, `extend`, `offset`, `mirror`,
`project`. B-Rep-Kern über OpenCASCADE ist **installiert und aktiv**, mit
`fillet_edges`, `chamfer_edges`, `shell_exact`, `draft_faces`, `thread_exact`,
`push_face` und fünf Skizzen-Ops.

**Wer es besser kann:** Fusion und Onshape beim Bedienen der Skizze —
Konstruktionsgeometrie, Zeichenkürzel im Fluss, Bemaßung während des Zeichnens.
Plasticity beim Gefühl für Flächen.

**Urteil: gleichauf rechnerisch, zurück bedienerisch.** Genau der Befund aus
`konzept-sindricad.md` B1, und er hat sich seither halb erledigt — die
Ändern-Gruppe steht, die restlichen Punkte aus `konzept-bedienung.md` Teil 4
nicht.

**Empfehlung:** Baustein A zu Ende führen. Kein neuer Befund, aber der teuerste
offene.

### 2.3 Mesh bearbeiten und reparieren (Säule C)

**Stand:** Eingangsstufe mit sechs Schritten, `repair`, Boolesche Kette mit vier
Rückfallstufen, `decimate_mesh`, `remesh_mesh`, `smooth_mesh`, `thicken`,
Feature-Erkennung in fünf Arten (`hole`, `face`, `edge_loop`, `pin`, `thread`)
mit stabilen IDs, Prüfbericht, Auto Split mit Verstiftung.

**Wer es besser kann:** Niemand mehr wirklich. Meshmixer ist eingestellt, 3D
Builder abgekündigt, MeshLab veraltet in der Bedienung, Netfabb und Magics
kosten industriell. Blender kann alles, verlangt aber Blender.

**Urteil: führend — und das ist die am meisten unterschätzte Position im ganzen
Programm.** Der häufigste Satz des Zielkunden lautet „ich habe hier ein STL und
brauche da ein Loch". Der Markt hat für genau diesen Satz zwei tote Programme
und ein Programm für Fortgeschrittene.

**Empfehlung:** Weg 1 zum Hauptversprechen der Website machen. Heute lautet die
Überschrift „Beschreibe das Teil" — das ist Weg 2 und stellt uns neben Zoo und
AdamCAD, wo wir mit deren Kapital konkurrieren. „Das heruntergeladene Teil
passt nicht — mach es passend" stellt uns neben zwei eingestellte Programme.

### 2.4 Generieren (Säule B)

**Stand:** ComfyUI lokal über HTTP, Hunyuan3D 2.1 als Graph in einer Datendatei,
`text_to_mesh` über SDXL als Zwischenschritt, danach zwingend die
Reparaturkette. Kein gehosteter Backend (P11 offen).

**Wer es besser kann:** Meshy und Tripo deutlich — Qualität, Tempo, Texturen,
und bei Meshy inzwischen automatische Farbzonen für AMS, eingebaut in
MakerWorld. Modly macht dasselbe lokal und kostenlos.

**Urteil: zurück, und das ist in Ordnung.** Wir haben hier keine Chance und
brauchen keine: Der Bauplan sagt selbst, dass generierte Meshes maßlich
unpräzise sind (§42). Unsere Rolle ist nicht das Erzeugen, sondern das, was
danach kommt — Reparatur, Prüfbericht, Bohrung, Verstiftung.

**Empfehlung:** Säule B nicht ausbauen, sondern **anschlussfähig machen**. Wer
mit Meshy oder Tripo erzeugt, soll das Ergebnis bei uns aufbereiten. Das ist
Weg 3 und kostet nichts außer einem Satz in der Vermarktung.

### 2.5 Der Agent

**Stand:** Anthropic über eigenen Schlüssel oder Ollama lokal, kein
Hersteller-SDK. Vorschlag als **eine** Transaktion (Regel 16), Prüfungen nach
jeder Op, Regelsammlung mit Version und Änderungsverlauf, Agenten-Suite mit 39
Referenzanfragen als Messung, MCP-Server im Fenster mit vier Auflagen
(standardmäßig aus, nur 127.0.0.1 dreifach geprüft, kein Quelltext, kein
Dateipfad).

**Wer es besser kann:** Autodesk beim Modell und beim Marketing. Blender-MCP bei
der Bekanntheit. Aber: Kein Wettbewerber misst seinen Agenten gegen eine feste
Anfragenmenge, keiner nimmt einen Vorschlag mit einem Undo vollständig zurück,
und keiner verbietet dem Modell, Koordinaten zu erfinden.

**Urteil: führend in der Bauart, unsichtbar in der Wirkung.** Die vier Sätze
oben sind das stärkste technische Argument, das wir haben, und sie stehen
nirgends, wo ein Käufer sie liest.

**Empfehlung:** Zwei Dinge. Erstens die Agenten-Suite als **Zahl**
veröffentlichen — eine gemessene Quote schlägt jedes Versprechen. Zweitens
„funktioniert mit Claude Code" als eigenen Abschnitt: Der MCP-Server ist gebaut,
sicher und niemand weiß davon.

### 2.6 Druckvorbereitung und Analyse

**Stand:** Eigene Schichtanalyse mit Überhang gesamt und schlimmster,
Inselerkennung je Lage, engste Stelle, Brückenweiten, Konturzahl,
Orientierungssuche über bis zu 2000 Lagen, Zeit- und Materialschätzung,
Einstellungsvorschläge mit Begründung je Wert (`SettingAdvice`), sauber getrennt
von gemessenen G-Code-Werten (Regel 14).

**Wer es besser kann:** Niemand vor dem Slicen. Orca hat die Kalibriersuite,
Prusa die organischen Stützen — beides **nach** der Konstruktion. Was keiner
tut: aus der Geometrie auf Einstellungen schließen **und den Grund dazusagen**,
solange das Teil noch änderbar ist.

**Urteil: führend, mit Abstand.** Das ist neben 2.3 die zweite echte
Alleinstellung.

**Empfehlung:** Der Prüfbericht ist das Verkaufsargument, nicht ein Fensterteil.
Er gehört als Bild auf die Website, mit einem Beispiel: „Diese Insel in Lage 47
kostet dich Stützmaterial — dreh das Teil um 12 Grad."

### 2.7 Wissen: Bausteine, Normteile, Material

**Stand:** 16 Bausteine, Normteile in sechs Tabellen (Schrauben, Muttern,
Scheiben, Einpressbuchsen, Magnete), 6 Materialien mit Spiel, Presspassung,
Bohrungskompensation, Elefantenfuß und Schwindung, 16 Druckerprofile,
Regelsammlung mit Version, Selbstkalibrierung über Testkörper (Toleranzleiter,
Wandstärkenleiter, Überhangfächer).

**Wer es besser kann:** Niemand in dieser Verbindung. Einzelne Bausteine gibt es
überall als Fremdbibliothek; die Verkettung „Toleranz ist ein Verweis ins
Materialprofil, das Profil kommt aus einem gedruckten Testkörper" gibt es nicht.

**Urteil: führend.** Dritte Alleinstellung.

**Empfehlung:** `auto:<material>` ist der beste Satz des ganzen Programms und
steht auf der Website nicht. Er beantwortet die Frage, die jeder Drucker
täglich stellt: *Wie viel Spiel muss ich lassen?*

### 2.8 Interoperabilität

**Stand:** Import STL, 3MF (auch als Baugruppe), OBJ, PLY, OFF, GLB, GLTF, STEP,
SVG, DXF. Export STL, 3MF, OBJ, PLY, STEP. Slicer-Übergabe an Prusa, Orca und
Cura mit geschriebenem Profil und Rückprüfung der Werte, G-Code zurücklesen.

**Wer es besser kann:** Die Slicer beim letzten Meter — Orca, Prusa, Bambu und
Cura schicken die Datei über das Netz an die Maschine. Bei uns liegt sie im
Ordner.

**Urteil: gleichauf beim Format, zurück beim Weg zur Maschine.** Befund B3 aus
`konzept-sindricad.md`, unverändert offen. Ebenso **B4: GLB kommt herein und
geht nicht hinaus** — die Formatliste bestätigt es heute noch.

**Empfehlung:** GLB-Export ist eine kleine Arbeit mit sichtbarem Nutzen (Teilen
ohne CAD-Programm) und sollte einfach passieren. Der Netzwerkdruck ist eine
Bauplanänderung (§28/§29 kennen ihn nicht) und braucht deine Ansage — siehe
Teil 5.

### 2.9 Oberfläche, Einstieg, Handbuch

**Stand:** 8 Beispielprojekte, sieben Touren, Handbuch mit erzeugter Referenz je
Registerkategorie, Erstinbetriebnahme, Befehlspalette, Fusion-Tastenbelegung,
Startbildschirm mit Ablagefeld, 103 Modelle durch die laufende Oberfläche
geprüft ohne einen Stolperer.

**Wer es besser kann:** Tinkercad beim ersten Klick. Alle Slicer bei der
Vertrautheit — der Kunde kennt deren Fenster schon.

**Urteil: gleichauf, mit einer Schwäche im Schaufenster.** Ein Handbuch, das
sich aus dem Register erzeugt und nicht veralten kann, ist mehr, als die meisten
freien Programme haben.

**Empfehlung:** Ein bewegtes Bild vom Weg 1 in unter 60 Sekunden. Der
`marketing/`-Ordner hat bereits Tonproben und eine Drehanleitung — das ist der
richtige Weg, er ist nur nicht zu Ende gegangen.

**Nachgetragen 13.08.2026: doch zu Ende gegangen.** `marketing/video/` enthält
vier fertige Filme — deutsch und englisch, jeweils quer (1080p) und hoch
(1080×1920) für die Kurzformate —, dazu die eingesprochene Tonspur. Offen ist
daran nichts mehr außer der Frage, *wo* sie laufen; die steht in Teil 7 als W1.

### 2.10 Plattform, Sprache, Reichweite

**Stand — und hier liegt der härteste Befund des Durchgangs:**

* **Kein macOS-Paket.** Die Suite läuft bei Tags auf macOS, paketiert wird nur
  Windows und Linux (`build.yml`, Job „Paket": `[windows-latest,
  ubuntu-latest]`). Fusion, Shapr3D, Plasticity, Orca, Prusa, Blender und
  Bambu Studio decken macOS alle ab.
* **Zwei Sprachen.** `app/i18n/locales/` enthält genau `en.json`; deutsch ist
  die Basis. Cura, Orca und Prusa liefern zweistellig viele Sprachen. Für ein
  Produkt zu 49 Euro im offenen Netzverkauf ist Spanisch, Französisch,
  Italienisch und Portugiesisch der billigste Reichweitengewinn, den es gibt —
  die Texte laufen ohnehin alle über `tr()` (Regel 20), das Gerüst steht.

**Urteil: zurück, in beidem.** Das sind keine Funktionslücken, sondern
Marktlücken — sie entscheiden nicht, ob jemand das Programm mag, sondern ob er
es überhaupt starten kann.

**Empfehlung:** Sprachen zuerst, weil billig und rein additiv. macOS als
Entscheidung, siehe Teil 5.

### 2.11 Sichtbarkeit und Ökosystem

**Stand:** Website deutsch und englisch, Handbuch, Rechtstexte, Paddle als
Abwicklung, Support über eine Adresse. Keine Presse, keine Gemeinschaft, kein
Katalogzugang.

**Wer es besser kann:** Alle. SindriCAD stand binnen eines Tages in der
Fachpresse. MakerWorld und Printables *sind* der Ort, an dem die Zielgruppe
ihre Modelle holt — und der Anpassungsfall wandert dorthin.

**Urteil: zurück.** Befund B5, unverändert und weiterhin der wichtigste.

**Empfehlung:** Siehe Teil 4, W1. Ohne diesen Punkt ist jeder andere ein
Vorbereiten für niemanden.

### 2.12 Preis, Lizenz, Vertrauen

**Stand:** 14 Tage Test, 49 € zur Einführung, später 79 €, Einmalkauf, alle
1.x-Updates, kein Konto, keine Telemetrie, keine Cloud, Betrachterbetrieb nach
Ablauf, erzeugte Modelle gehören dem Nutzer.

**Wettbewerb:** Fusion Personal kostenlos mit spürbaren Fesseln (10 aktive
Dokumente, eingeschränkte Exportformate). Plasticity ~150 $ einmalig mit
12 Monaten Aktualisierungen. Shapr3D ~299 $/Jahr, kein Einmalkauf. Slicer und
FreeCAD kostenlos.

**Urteil: führend in der Aufstellung.** Einmalkauf ohne Konto ist 2026 selten
genug, um selbst ein Argument zu sein — der Sprung von kostenlos auf 299 $/Jahr
lässt bei Shapr3D erklärtermaßen eine Lücke, und 49 € sitzen genau darin.

**Ein Befund am Rande, der sich als Fehlbefund erwiesen hat:** Die Website
nennt *„77 Operationen im Register"* neben *„16 geprüfte Bausteine"*, und ein
erster Zähllauf kam auf 61 — die Zahl sah nach einer Summe mit doppelt
gezählten Bausteinen aus. Sie ist keine: jeder Baustein ist zugleich eine
registrierte Operation (`insert_*`), und mit vollständig geladenem Register
sind es tatsächlich 77, davon 16 aus der Bibliothek. Der erste Lauf hatte das
Register über `walk_packages` gefüllt statt über `load_operations()` und die
sechzehn deshalb nicht gesehen. `tests/test_website.py` prüft die Zahl gegen
das Register — die Suite hat den Fehlbefund gefangen, bevor er auf der Seite
stand.

---

## Teil 3 — Wo Solidon allein steht

Vier Dinge, die im gesamten recherchierten Feld kein anderes Programm in dieser
Verbindung hat. Sie sind die Antwort auf „warum nicht das kostenlose":

1. **Das fremde Modell änderbar machen** — Feature-Erkennung mit stabilen IDs,
   Rückfallkette, Prüfbericht. Der Markt hat dafür zwei eingestellte Programme.
2. **Druckbarkeit vor dem Slicen, mit Begründung** — Inseln, Brücken,
   Orientierungssuche, Einstellungsvorschlag mit Grund und ausgewiesener
   Herkunft.
3. **Toleranz als Verweis, nicht als Zahl** — `auto:<material>`, gespeist aus
   gedruckten Testkörpern.
4. **Ein Agent, der nichts erfindet** — keine Koordinaten, ein Vorschlag ist
   eine Transaktion, Prüfung nach jeder Op, gemessen gegen 39 Referenzanfragen.

Die ersten drei stehen auf der Website nicht oder nur beiläufig. Die
Überschrift verkauft heute Säule A — den einzigen Bereich, in dem wir gegen
Autodesks Foundation-Modelle antreten.

---

## Teil 4 — Die Lücken, nach Kaufrelevanz

Sortiert danach, wie viele Käufe der Punkt verhindert — nicht danach, wie groß
die Arbeit ist.

| | Lücke | Größe | Stand am 13.08.2026 |
|---|---|---|---|
| **W1** | **Niemand weiß, dass es uns gibt.** | Entscheidung | **offen** — B5, siehe Teil 7 |
| **W2** | **Kein macOS-Paket** — ein spürbarer Teil der Zielgruppe kann nicht starten | mittel + Entscheidung | **offen** — Entscheidung, siehe Teil 7 |
| ~~W3~~ | ~~Nur zwei Sprachen — ES, FR, IT, PT fehlen, Gerüst steht~~ | klein je Sprache | **erledigt** — sechs Sprachen, je 2279 Einträge |
| ~~W4~~ | ~~Weg 1 ist unsere Stärke und nicht unser Versprechen — Website führt mit Säule A~~ | klein | **erledigt** — Überschrift ist Weg 1 |
| **W5** | **Letzte Meile zum Drucker** — Datei bleibt im Ordner | mittel + Bauplanänderung | **offen** — B3, Entscheidung, siehe Teil 7 |
| ~~W6~~ | ~~Acht Texturmuster, die niemand sieht~~ | klein | **erledigt** — Musterbild auf der Seite |
| ~~W7~~ | ~~GLB geht nicht hinaus~~ | klein | **erledigt** — GLB-Export gebaut |
| ~~W8~~ | ~~Skizze bedienerisch halb — Ändern-Gruppe steht, Rest offen~~ | mittel | **erledigt** — alle neun Punkte |
| **W9** | **Kein Weg vom Modellkatalog zu uns** — der Anpassungsfall wandert zu MakerWorld | Entscheidung | **offen** — Entscheidung, siehe Teil 7 |

**Fünf von neun sind zu, und vier davon nicht durch dieses Dokument.** W4, W6,
W7 und W8 wurden erledigt, während dieses Konzept sie als offen führte — von
P15 und der Website-Runde, die eigene Wege gingen. Nachgemessen am 13.08.2026,
Punkt für Punkt gegen den Code statt gegen die Erinnerung:

* **W4** — die Überschrift lautet „Das heruntergeladene Teil passt nicht. Mach
  es passend." Damit führt Weg 1 statt Säule A, genau wie es die Empfehlung in
  2.3 verlangt. Auch der Rest steht: der Prüfbericht mit Insel-Beispiel, die
  Abgrenzung („Was Solidon3D nicht ist"), der Anschluss an fremde Generatoren
  („Wenn das Modell aus einer KI kommt"), Claude Code und der MCP-Server. Die
  Agenten-Suite steht als **Zahl** da — 28 von 39, 98 % der Werkzeugaufrufe —
  und `auto:<material>` in Klartext: *Toleranzen holen sich ihren Wert aus dem
  Materialprofil, statt als Konstante im Modell zu verschwinden.*
* **W6** — die acht Muster stehen als Bild auf der Seite, hell und dunkel, mit
  einem Alternativtext, der jedes einzelne benennt.
* **W7** — `glb` steht in `ExportFormat`, `_glb_bytes()` schreibt es mit Namen
  und Farben. Import **und** Export.
* **W8** — alle neun Punkte aus `konzept-bedienung.md` Teil 4: Ursprung und
  Maßstab, die Zeichenkürzel L R C A D T O X mit Esc, ausdrücklich **nur im
  Skizzenmodus** belegt (damit ist der R/C-Widerspruch zur Fusion-Belegung
  aufgelöst), Trimmen/Verlängern/Versetzen/Spiegeln, Projizieren und
  Hilfsgeometrie, Maß beim Zeichnen eintippen, Aufleuchten der Geometrie zur
  Bedingungsliste, ein sichtbarer *Fertig* in einer eigenen Zeile — die die
  alte Werkzeugzeile ersetzt, statt sich unter sie zu stellen.

Was das über das Dokument sagt, nicht über die Arbeit: **eine Lückenliste
altert schneller als der Code.** Wer sie liest, muss messen, bevor er baut —
sonst baut er ein zweites Mal, was schon steht.

---

## Teil 5 — Was wir nicht übernehmen

| Nicht übernehmen | Warum |
|---|---|
| **Wettlauf um Text→Mesh-Qualität** | Meshy und Tripo haben Kapital und Modelle. Unsere Rolle beginnt hinter deren Ausgabe (§42). |
| **Wettlauf um generative CAD** | Autodesk baut Foundation-Modelle für Geometrie. Unser Gegenargument ist Lokalität und Determinismus, kein größeres Modell. |
| **Baugruppen, Gelenke, Zeichnungsableitung** | Steht als Abgrenzung im README und bleibt richtig. |
| **Eigener Slicer, Cloud, Konto, Telemetrie, Plugin-System** | §41 und AGENTS.md, unverändert. |
| **Sculpting und Freiform** | Blender und Plasticity, beide besser, einer kostenlos. |
| **Abo** | Der Einmalkauf ist ein Verkaufsargument, kein Zugeständnis. |

---

## Teil 6 — Empfohlene Reihenfolge

Nach Wirkung je Aufwand, nicht nach Bereich. **Die Punkte 1 bis 4 sind
abgearbeitet; was bleibt, ist Punkt 5 — und das ist keine Arbeit, sondern eine
Entscheidung.**

1. ~~**W4, W6**~~ — **erledigt.** Eine Runde an Website und Vermarktung: Zahl
   richtiggestellt, Weg 1 nach vorn, Texturen mit Bild. Kein Code, größter
   sichtbarer Gewinn.
2. ~~**W3**~~ — **erledigt am 13.08.2026.** Spanisch, Französisch, Italienisch,
   Portugiesisch liegen vollständig in `app/i18n/locales/`, je 2279 Einträge,
   abgenommen von `tests/test_translations.py` (104 Fälle) und mitgetragen von
   Handbuch- und Website-Tests (460 Fälle). Die Vorhersage „additiv, prüfbar"
   hat gestimmt: keine Zeile Code, die eine Sprache kennt. Was sie nicht
   vorhergesagt hat, war der Preis der Parallelität — acht gleichzeitig
   arbeitende Agenten gegen einen Katalog, der während des Laufs um fünfzehn
   Schlüssel wuchs und damit jeden Index über der ersten Einfügestelle
   verschob. Der Ausweg steht in `.claude/i18n-wip/STAND.md`: eine eingefrorene
   Basis, Nachträge über den Quelltext statt über den Index. **Offen bleibt**
   die Nachaufnahme der Handbuchbilder je Sprache — eigener Schritt, läuft
   nicht offscreen.
3. ~~**W7**~~ — **erledigt.** GLB wird hinausgeschrieben, mit Namen und Farben.
4. ~~**W8**~~ — **erledigt.** Baustein A steht, alle neun Punkte aus
   `konzept-bedienung.md` Teil 4.
5. **W1, W2, W5, W9** — Entscheidungen, siehe Teil 7. **Hier steht die Arbeit
   jetzt.** Kein Code wartet mehr davor, und drei der vier kosten Geld oder
   Bauplan, nicht Tage.

---

## Teil 7 — Was du entscheiden musst

Vier Fragen, die dieses Dokument nicht beantworten kann:

1. **macOS ausliefern — ja oder nein?** Die Suite läuft dort bereits grün. Es
   fehlen der Paketierschritt, eine Signierung bei Apple (jährliche Gebühr) und
   die Bereitschaft, eine dritte Plattform zu stützen. Nein ist eine
   vertretbare Antwort — dann sollte die Website es aber aussprechen, statt es
   auszulassen.

2. **G-Code an die Maschine senden — Bauplanänderung?** §28 meint mit „Drucker"
   das Zurücklesen, nicht das Senden. Senden ist kein Erzeugen, der eigene
   Slicer bleibt ausgeschlossen. Wenn ja, dann über ein offenes Protokoll für
   viele Maschinen, nicht für eine.

3. **Weg vom Modellkatalog — bauen oder auslassen?** Der Anpassungsfall ist
   unsere Stärke, und er wandert gerade auf die Modellseiten von MakerWorld.
   Ein lesender Zugriff auf eine URL widerspricht „keine Cloud" nicht, aber er
   ist eine Netzabhängigkeit im Einstieg. Auslassen ist vertretbar; dann muss
   der Weg „heruntergeladene Datei ziehen und ablegen" umso sichtbarer sein.

4. **Wer schreibt über uns?** W1 ist kein Entwicklungspunkt. Solange er offen
   ist, arbeiten alle anderen Punkte für ein leeres Haus.

---

*Beschlossenes wandert nach `ROADMAP.md`; der Bauplan ändert sich nur mit
Ansage.*
