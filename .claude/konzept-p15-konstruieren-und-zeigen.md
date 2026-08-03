# Konzept P15 — Konstruieren und Zeigen

Entwurf, noch nicht beschlossen. Anlass: vier Quellen (SindriCAD, Meshy 3D
Agent, der Software-Ticker von 3Druck.com) und der Auftrag, sie in **Logik,
Steuerung, Aussehen, Optik und Funktionen** nicht einzuholen, sondern zu
übertreffen.

Aufbau: erst was die Quellen zeigen (§1), dann der **gemessene** Ist-Stand
(§2), dann das Delta (§3), dann die Leitentscheidungen (§4), die Etappen (§5),
die Abgrenzung (§6) und die Folgen für Bauplan und Roadmap (§7).

---

## 1. Was die Quellen zeigen

### 1.1 SindriCAD — der direkte Vergleich

Öffentliche Beta seit dem 03.08.2026, AGPL, kostenlos, Linux/Windows/macOS,
Einzelentwickler hinter TinkerAtlas, spendenfinanziert. Entstanden aus einem
Linux-Problem mit einem kommerziellen CAD.

**Der beworbene Arbeitsablauf** steht wörtlich auf der Produktseite und ist
die eigentliche Aussage: *Profil skizzieren → zum Körper ziehen → Kanten
runden → eine echte Textur in eine Fläche pressen → an den Slicer.* Dazu der
Satz, der die Parametrik verkauft: eine Maßänderung früh in der Kette baut das
ganze Teil neu auf.

| Beworben | Inhalt |
|---|---|
| Solid modeling | Extrude, Revolve, Loft, Fillet, Chamfer, Shell, **Press/Pull**, **Mirror**, **Pattern** |
| Parametric history | jeder Schritt änderbar, benannte Parameter, echte Maße |
| **Printable surface textures** | Rändel, Wabe, Welle, Voronoi — **als echte Geometrie**, nicht als Bump-Map |
| Multi-color output | Farben je Teilbereich, 3MF für Mehrfarbdrucker |
| Slicer-ready export | raus: STL, STEP, 3MF · rein: STEP, GLB |
| Familiar shortcuts | Kürzel und Arbeitsweise der verbreiteten Profi-CAD |
| Sonstiges | Messen vor dem Drucken, Schnitt durch das Teil zur Wandstärkenprüfung |

**Positionierung:** *„built for printing, not for engineering drawings."*
Genau Formwerks Satz — von jemand anderem gesagt.

**Schwächen, die die Seite selbst nennt:** Beta mit rauen Kanten, unsignierte
Builds, macOS verweigert den Start, Einzelperson ohne Zeitbudget. Und
inhaltlich: die Werkzeugliste endet bei der Geometrie. Kein Wort über
Schichtanalyse, Stützen, Toleranzen, Materialprofile, Passungen, Zerlegen
übergroßer Teile oder Slicer-Rückkopplung.

### 1.2 Meshy 3D Agent — die Gegenthese

Kein Konstruieren, sondern Gespräch: Beschreibung, Foto oder Kinderzeichnung
rein, in etwa einer Minute ein texturiertes, wasserdichtes Modell raus.
Mehrere Richtungen zur Auswahl, Verfeinerung im selben Gespräch statt neuer
Generierung, Druckbarkeitsprüfung vor der Ausgabe, Übergabe an Bambu Studio
mit einem Klick, acht Exportformate.

**Und das Eingeständnis, das für uns zählt:** *„Kein KI-Generator kann CAD
vollständig ersetzen."* Präzise Bauteile mit engen Toleranzen bleiben
parametrischen Werkzeugen vorbehalten; Kanten werden geglättet, Details unter
1 mm werden fragil, exakte Abmessungen sind nicht garantiert, die Generierung
enthält Zufall.

Das ist wörtlich Bauplan §42 („Generierte Meshes sind maßlich unpräzise; für
Passungen taugen sie nicht"). Die Marktführer der Generierung sagen selbst,
wo ihre Grenze liegt — und Formwerks Weg 3 endet nicht dort, er fängt dort an:
Reparaturkette, Prüfbericht, Zerlegen, Verstiften, Export.

### 1.3 Der Ticker — wohin sich der Markt bewegt

Aus der Software-Kategorie von 3Druck.com, Juli/August 2026, in der
Reihenfolge, in der sie dort stehen:

| Meldung | Was es für uns heißt |
|---|---|
| **FreeCAD über MCP von Claude/ChatGPT steuerbar** | KI-Steuerung wandert von der eingebauten Schicht zur **offenen Schnittstelle** |
| **Hi3D V3.0**, **Modly**, **Meshy 400 M$**, **Tripo 150 M$** | Generierung ist kapitalisiert und wird Ware; **lokal** (Modly) ist das Unterscheidungsmerkmal |
| **FilaSim** — freie Belastungssimulation für FDM im Browser | Festigkeit wird eine Erwartung an Druck-Software |
| **Spherene NXT** — adaptive Metamaterial-Innenstrukturen | Leichtbau/Gitter wandert vom Slicer ins Modell |
| **Prusa EasyPrint-Abo sorgt für Kritik** | Zahlbereitschaft ja, Abo nein — bestätigt den Einmalkauf |
| **Watchtower**, **Lumina Studio**, **OrcaSlicer-Forks**, **meshStep**, **SketchForge**, **PaintPort** | die Szene baut viele kleine, lokale, quelloffene Werkzeuge |

Zwei Signale sind unmittelbar handlungsrelevant: **MCP** und **Gitterstrukturen**.

---

## 2. Ist-Stand Formwerk — gemessen, nicht behauptet

Erhoben am 03.08.2026 gegen den Arbeitsbaum, nicht gegen die Roadmap:

* **55 Operationen** im Register, 16 Kategorien; **16 Bausteine**
* **2211 Tests grün** (`-m "not performance"`, 158 s), keine Importfehler
* Import laut Filter: STL, 3MF, OBJ, **GLB**, GLTF, PLY, OFF, STEP, STP, SVG, DXF
* Export: STL, 3MF (als Baugruppe), OBJ, PLY, STEP
* Skizzen: 5 Ops, 9 Bedingungsarten (`distance`, `coincident`, `horizontal`,
  `vertical`, `parallel`, `perpendicular`, `tangent`, `symmetric`, `fixed`),
  eigener Solver auf scipy, 200 Bedingungen in 90 ms
* Formgebung: `fillet_edges`, `chamfer_edges`, `shell_exact`, `draft_faces`,
  `thread_exact` — exakt gegen OpenCASCADE
* Tastenkürzel: **6 an Operationen**, 21 im Fenster
* Viewport: PyVista/VTK, vier Darstellungsarten, Standardbeleuchtung

### 2.1 Was Formwerk hat und in keiner der Quellen vorkommt

Das ist die Liste, die die Ausgangslage richtigstellt — der Vergleich beginnt
nicht bei null:

Schichtanalyse mit Überhängen, Inseln, Brückenweiten, Stützvolumen und
Minimalbreite · Druckeinstellungen **aus der Geometrie abgeleitet** mit
Begründung je Vorschlag · Hinweg zum Slicer und Gegenprobe aus dem erzeugten
G-Code · Materialprofile mit Kalibrierung, Toleranzen als Verweise
(`auto:<material>`) statt als Zahlen · Passungen als geprüfte Beziehung im
Dokument · Material **je Körper**, nicht je Projekt · Auto Split mit
Verstiftung und kalibriertem Spiel · Bausteinbibliothek mit Normteiltabelle ·
Feature-Erkennung mit stabilen IDs und Provenienz über zehn Operationen
hinweg · sieben Analysekarten · Variantengenerator · Prüfstück aus der echten
Geometrie geschnitten · Deckel und Schraubdeckel aus der gemessenen Öffnung ·
KI-Agent lokal oder über eigenen Schlüssel, **jeder Vorschlag genau eine
rücknehmbare Transaktion** · Handbuch mit 25 Seiten und Touren · optionaler
B-Rep-Kern.

**Befund:** In der Druckintelligenz ist Formwerk den Quellen nicht ähnlich —
es spielt eine andere Liga. Was fehlt, sind Konstruktionswerkzeuge, die jedes
CAD hat, und eine Ansicht, die aussieht wie das Jahr 2026.

---

## 3. Das Delta — zwölf Punkte

Sortiert nach dem, was ein Fremder in den ersten fünf Minuten merkt.

| # | Lücke | Quelle | Schwere |
|---|---|---|---|
| **D1** | **Ansicht ohne Kantenglättung, ohne Umgebungsverdeckung, ohne Schatten, ohne Studiolicht** | Optik | **hoch** — jedes Bildschirmfoto |
| **D2** | **Oberflächentexturen fehlen ganz** (Rändel, Wabe, Welle, Voronoi) | SindriCAD | **hoch** — deren beworbenes Kernfeature |
| **D3** | **Skizzieren ist ein modaler Dialog, keine Ebene im Fenster** | SindriCAD, Bauplan §30.1 | **hoch** — Bauplanabweichung |
| **D4** | **Kein Muster** (linear, kreisförmig, auf Fläche) | SindriCAD | hoch |
| **D5** | **Kein Press/Pull** — keine Fläche direkt greifbar | SindriCAD | mittel |
| **D6** | **6 Kürzel an 55 Operationen**, kein Mainstream-Satz | SindriCAD | mittel |
| **D7** | **Bild und Skizze sind kein Chat-Eingang**, getrennter Dialog | Meshy | mittel |
| **D8** | **Keine Variantenauswahl beim Generieren** — ein Wurf, kein Vorschlagsfeld | Meshy | mittel |
| **D9** | **Keine offene Schnittstelle nach außen** (MCP) | FreeCAD-Meldung | mittel |
| **D10** | **Keine Gitter-/Leichtbaustrukturen** im Modell | Spherene | mittel |
| **D11** | Keine Festigkeitsabschätzung | FilaSim | niedrig |
| **D12** | Kein Modellvergleich zweier Fassungen | §41 | niedrig |

**D3 ist kein Wunsch, sondern ein offener Punkt:** Bauplan §30.1 verlangt für
Stufe zwei ausdrücklich *„der grafische Editor **im Viewport** (Ebene
anklicken, zeichnen, Bedingungen über Werkzeugleiste und Kontextmenü)"*.
Gebaut ist `SketchEditorDialog(QDialog)`, erreichbar über ein Feld im
Operationsdialog. Die Roadmap hakt es ab; der Bauplan gewinnt.

---

## 4. Leitentscheidungen

### E1 — Jede übernommene Funktion bekommt die Druckintelligenz, die schon da ist

**Das ist der ganze Trick, und er kostet fast nichts.** Formwerk kennt Düse,
Schichthöhe, Material, Volumenstrom, Bauraum und die Schichtanalyse. Jede
Funktion, die wir von SindriCAD übernehmen, weiß damit etwas, das dort niemand
weiß:

* Eine **Textur**, deren Struktur schmaler ist als die Düse, wird nicht
  stillschweigend gedruckt — die Operation sagt es, mit der Zahl, und schlägt
  die Teilung vor, die passt.
* Ein **Muster** prüft Bauraum und Kollision, bevor es 40 Kopien anlegt.
* Ein **Press/Pull** meldet, wenn die Wand danach unter der Mindestwandstärke
  des Materials liegt.
* Eine **Skizze** im Viewport zeigt die Bauraumgrenze und die Schichtrichtung.

SindriCAD kann seine Texturen anbieten. Es kann nicht sagen, ob sie druckbar
sind. **Das ist der Unterschied zwischen gleichziehen und übertreffen.**

### E2 — Die Optik kommt aus Daten, nicht aus Dekoration

Formwerk weiß, aus welchem Material jeder Körper ist (`SceneObject.material`,
seit „Eine Szene ist nicht ein Material") und welche Filamentfarbe die
Druckeinstellungen tragen. Die Ansicht zeigt das bisher nicht — sie malt alles
grau.

Ein PETG-Teil glänzt anders als ein TPU-Teil, und ein Teil in der Farbe des
geladenen Filaments ist eine **Vorschau auf das Ergebnis**, keine Spielerei.
Zusammen mit Umgebungsverdeckung, Kontaktschatten auf der Druckplatte und
Feature-Kanten statt Dreieckskanten ergibt das ein Bild, das kein
Vergleichsprodukt hat — weil keines die Daten dafür hat.

Regel 18 bleibt: Bedeutung nie allein über Farbe. Die Materialdarstellung ist
Darstellung, nicht Bedeutung; alles Bedeutungstragende behält seine zweite
Kodierung.

### E3 — Skizzieren wird ein Modus, kein Dialog

Der Editor zieht aus dem Dialog in den Viewport: Fläche oder Hauptebene
anklicken → *Skizze beginnen* → die Kamera stellt sich senkrecht, der Rest der
Szene wird durchscheinend, die Werkzeugleiste wechselt → zeichnen, Bedingungen
setzen, Maße als Ausdrücke → *Fertig* öffnet die Operation, die sie verbraucht.

**Was sich nicht ändert:** Die Skizze bleibt Parameterwert der Operation
(§30.1), es entsteht kein zweiter Dokumentbegriff, `change_params` und der
Cache gelten unverändert, der Agent bekommt weiter nur Grundformen. Der
bestehende `SketchCanvas` trägt die Zeichenlogik und wird
wiederverwendet — der Dialog fällt weg, die Zeichenfläche nicht.

### E4 — Texturen sind eine eigene Kategorie, keine Boolesche Operation

Neue Registerkategorie `surface`. Eine Textur ist eine Operation auf einer
**gewählten Fläche** (`applies_to=["face"]`), mit Muster, Teilung, Tiefe und
Ausrichtung als Parametern — alle als Ausdrücke der Parametergrammatik, also
über einen Projektparameter durchdrehbar.

Umsetzung gegen `manifold3d`, nicht gegen den B-Rep-Kern: eine Wabenprägung
mit tausenden Zellen ist als exakter Körper unbezahlbar und als Netz eine
Vereinigung. Der Körper wird dabei zum Netz — `kind` folgt dem Körper (P12),
und die Operation sagt das vorher.

**Der Katalog geht über SindriCAD hinaus:** Rändel gerade, Rändel gekreuzt,
Wabe, Welle, Voronoi, Noppen, Riffel, Stipple. Acht statt vier, und jede mit
der Prüfung aus E1.

### E5 — Gitterfüllung gehört ins Modell, nicht in den Slicer

Der Slicer füllt mit Gitter, was er für innen hält. Er kennt aber weder die
Lastrichtung noch die Stelle, an der es dünn sein darf. `lattice_fill` füllt
einen ausgehöhlten Körper mit einer Gyroid- oder Wabenstruktur als **echte
Geometrie** — damit reist sie im 3MF mit, überlebt jeden Slicer und ist eine
Zahl im Steckbrief statt einer Prozenteinstellung.

Das ist Spherenes Thema, lokal und ohne Browser. Und es ist kein
G-Code-Slicer (§22.5) — es ist Geometrie vor dem Slicer.

### E6 — Ein Kürzelsatz, zwei Belegungen

Nicht „Formwerk-Kürzel" gegen „Fusion-Kürzel" als Weltanschauung, sondern eine
Tabelle in den Einstellungen mit zwei Voreinstellungen. Die Vorgabe bleibt die
heutige; wer aus Fusion oder Onshape kommt, schaltet um und findet E, Q, F,
M, D, L, C dort, wo er sie erwartet.

Das Kürzel steht weiterhin **im Register** (Leitprinzip 3, eine Quelle); die
Belegungstabelle legt sich darüber wie die Menügruppen aus P14 (E5 dort).

### E7 — Der Chat nimmt Bilder, und Generieren liefert Vorschläge

Meshys zwei echte Bedienideen, beide ohne Cloud nachbaubar:

* **Ein Bild ins Chatfenster ziehen** ist eine Eingabe wie ein Satz. Der
  Generierungsdialog bleibt für den, der ihn sucht; der Weg über den Chat ist
  der kürzere.
* **Vier Vorschläge statt einem.** `text_to_mesh` mit vier Startwerten,
  nebeneinander als Kacheln, jede mit ihrem Steckbrief-Auszug (Volumen,
  geschlossen ja/nein, Dreiecke). Ausgewählt wird einer; die anderen
  verschwinden, ohne je Objekte geworden zu sein.

Das ist kein Widerspruch zu Leitprinzip 4: jeder Vorschlag trägt seinen
Startwert, und der ausgewählte reist in die Quelle wie bisher.

### E8 — MCP: Formwerk als Werkzeug für fremde KI

Die FreeCAD-Meldung beschreibt genau das, was Formwerk fast fertig hat:
`app/core/agent/tools.py` erzeugt die Werkzeugschemata **aus dem Register**.
Ein MCP-Server ist eine dünne Schicht darum plus Transport.

Auflagen, ohne die es nicht gebaut wird:

1. **Standardmäßig aus.** Ein Schalter in den Einstellungen, nicht beim ersten
   Start eingeschaltet.
2. **Nur lokal** (`127.0.0.1`), kein Netzwerkzugriff von außen.
3. **Jeder Fernzugriff ist eine Transaktion** (Regel 16) und steht im Verlauf
   mit dem Vermerk, dass er von außen kam (§26.4).
4. **Kein Dateisystemzugriff über die Schnittstelle**, keine Pfade als
   Parameter, kein OpenSCAD-Quelltext von außen (Regel 11, 13).

Das ist **kein Plugin-System** (§41): es erweitert nicht die Anwendung, es
steuert sie fern — dieselben Ops wie ein Menüeintrag, Leitprinzip 1.

### E9 — Was nicht aus dem Vergleich kommt, wird nicht gebaut

FEM (D11) bleibt draußen. Begründung in §6.

---

## 5. Etappen

Sieben Einheiten, jede für sich committierbar, jede mit grüner Suite am Ende.
Die Reihenfolge folgt der Sichtbarkeit: Etappe 1 ändert jedes Bildschirmfoto
und jede Handbuchabbildung, Etappe 2 löst die Bauplanabweichung.

### Etappe 1 — Die Ansicht sieht aus wie 2026 (D1, E2)

- [ ] Kantenglättung an (`enable_anti_aliasing`), Umgebungsverdeckung
      (`enable_ssao`), Studiobeleuchtung statt Standardlicht
- [ ] Kontaktschatten auf der Druckplatte; Platte mit Raster und Maßstab
- [ ] **Feature-Kanten statt Dreieckskanten** — dieselbe Silhouettenlogik, die
      `core/drawing` fürs Handbuch schon rechnet; ein Mesh soll aussehen wie
      ein Körper, nicht wie ein Netz
- [ ] **Materialdarstellung aus dem Dokument** (E2): Glanz nach Material,
      Farbe nach Filament; abschaltbar, Vorgabe an
- [ ] Leistungsschutz: alle Zutaten schalten sich ab, wo sie das Budget aus
      §31 reißen; die Anzeige-Dezimierung aus P14 Etappe 7 bleibt davor
- [ ] Handbuchbilder neu aufnehmen (unter der echten Plattform, nie offscreen)

*Abnahme:* Ein 20-mm-Würfel neben einem gedruckten Bild ist als Material
erkennbar. Kein Messwert aus `tests/test_performance.py` fällt über die
25-%-Schwelle.

### Etappe 2 — Skizzieren im Viewport (D3, E3)

- [ ] Skizzenmodus: Ebene wählen (Hauptebene oder planare Fläche), Kamera
      senkrecht, Szene durchscheinend, eigene Werkzeugleiste
- [ ] `SketchCanvas` wandert in den Viewport-Aufsatz, der Dialog entfällt
- [ ] Bauraumgrenze und Schichtrichtung sichtbar (E1)
- [ ] Freiheitsgrade und Konflikte weiter in der Statuszeile, nicht als Dialog
- [ ] `Escape` verlässt den Modus wie jedes andere Werkzeug (P14 Etappe 6)

*Abnahme:* Von der leeren Szene bis zum extrudierten Profil ohne einen einzigen
modalen Dialog. Bestehende Skizzen aus Projektdateien öffnen unverändert.

### Etappe 3 — Oberflächentexturen (D2, E1, E4)

- [ ] Kategorie `surface` im Register; Bauplan §25 ergänzen
- [ ] `apply_texture` mit acht Mustern, Parametern Teilung/Tiefe/Winkel/Fläche
- [ ] **Druckbarkeitsprüfung** gegen Düse, Schichthöhe und Überhangwinkel;
      unter der Düsenbreite ein Befund mit Vorschlag, kein stiller Druck
- [ ] Geometrietests gegen den Korpus: wasserdicht nach der Prägung, Volumen
      in der erwarteten Richtung, keine Selbstdurchdringung an den
      Parametergrenzen
- [ ] Übersetzungen und Handbuchseite

*Abnahme:* Ein Rändelgriff auf einem Gehäuse, mit 0,4-mm-Düse geprüft; eine
Teilung von 0,3 mm wird abgelehnt, mit der Zahl und dem Vorschlag.

### Etappe 4 — Muster und Press/Pull (D4, D5)

- [ ] `pattern_linear` (Richtung, Anzahl, Abstand), `pattern_circular` (Achse,
      Anzahl, Winkel), beide mit Bauraum- und Kollisionsprüfung (E1)
- [ ] `push_face` — gewählte Fläche entlang ihrer Normalen versetzen, exakt
      auf B-Rep, als Extrusion auf dem Mesh-Kern; Wandstärkenprüfung danach
- [ ] Gizmo greift die Fläche direkt; ein Zug ist **eine** Transaktion (§18.10)

*Abnahme:* Ein Lochbild aus einer Bohrung in zwei Klicks. Eine Fläche, deren
Zug die Wand unter das Materialminimum bringt, meldet es vor dem Anwenden.

### Etappe 5 — Gitterfüllung (D10, E5)

- [ ] `lattice_fill`: Gyroid, Wabe, Würfelgitter; Zellgröße und Wandstärke als
      Parameter, Mindestwandstärke aus dem Materialprofil (Regel 7)
- [ ] Kennzahl im Steckbrief: Volumenanteil, Masse gegen den vollen Körper
- [ ] Zusammenspiel mit `hollow_object`: füllen setzt aushöhlen voraus, und
      die Operation sagt das, statt es stillschweigend selbst zu tun

*Abnahme:* Ein 50-mm-Würfel, gefüllt, wiegt nachgerechnet weniger und bleibt
geschlossen. Die Schichtanalyse findet keine Insel.

### Etappe 6 — Steuerung (D6, D7, D8, E6, E7)

- [ ] Kürzeltabelle mit zwei Belegungen, umschaltbar in den Einstellungen
- [ ] Bild ins Chatfenster ziehen als Eingabe
- [ ] Vier Generierungsvorschläge als Kacheln, einer wird übernommen
- [ ] Befehlspalette nimmt die neuen Operationen auf (fällt aus dem Register)

*Abnahme:* Wer aus Fusion kommt, findet Extrude, Press/Pull, Fillet und Move
auf den erwarteten Tasten. Ein Foto im Chat erzeugt ein Modell, ohne dass
jemand einen Dialog gesucht hat.

### Etappe 7 — MCP-Schnittstelle (D9, E8)

- [ ] Server auf `127.0.0.1`, standardmäßig aus, Schalter in den Einstellungen
- [ ] Werkzeuge aus `agent/tools.py`, keine eigene zweite Liste
- [ ] Jeder Fernaufruf eine Transaktion mit Herkunftsvermerk
- [ ] Sicherheitstests: kein Pfadparameter, kein Quelltext, kein Zugriff von
      außerhalb des Rechners — jeder abgewiesen, bevor gerechnet wird

*Abnahme:* Claude Code baut über MCP ein Gehäuse mit Deckel, und ein Strg+Z im
Fenster nimmt jeden Schritt einzeln zurück.

---

## 6. Was nicht gebaut wird — und warum

* **FEM-Festigkeitssimulation** (FilaSim, D11). Ein eigener Fachbereich mit
  eigener Validierungspflicht: Anisotropie des Schichtaufbaus, Haftung
  zwischen den Lagen, Kerbwirkung an Ecken. Eine Zahl, die falsch ist und
  geglaubt wird, ist schlimmer als keine Zahl. Wenn es kommt, dann als
  Ampel („diese Wand ist für ein tragendes Teil dünn") aus der
  Schichtanalyse — nicht als Spannungsplot.
* **Cloud-Generierung.** §27 knüpft das an nachweisbare Nachfrage; sie fehlt
  weiter. Meshys 400 Millionen ändern daran nichts — sie bestätigen nur, dass
  wir dort nicht gewinnen können und auch nicht müssen.
* **Eigener G-Code-Slicer.** Unverändert (§22.5). Die Gitterfüllung aus E5 ist
  Geometrie **vor** dem Slicer, kein Ersatz für ihn.
* **Browser-Version.** Steht auf der Nicht-bauen-Liste (§41) und bleibt dort.
* **Plugin-System.** Der MCP-Server ist keines (E8).
* **Verzweigungen im Op-Stack.** Die vier Generierungsvorschläge aus E7 sind
  keine Zweige — sie werden Vorschläge genannt, weil genau einer ein Objekt
  wird und die anderen nie eines waren.

---

## 7. Folgen für Bauplan und Roadmap

Nichts davon wird ohne Ansage geändert. Was zu ändern wäre:

| Stelle | Änderung |
|---|---|
| **§25 Operationskatalog** | neue Kategorie **Oberfläche** (Textur, Gitterfüllung); **Muster** unter Transformation; **Fläche versetzen** unter Formgebung |
| **§18 Viewport** | neuer Abschnitt Darstellungsqualität: Kantenglättung, Umgebungsverdeckung, Kontaktschatten, Feature-Kanten, Materialdarstellung aus dem Dokument |
| **§30.1** | Stufe zwei präzisieren: der Editor **ist** ein Viewport-Modus; der heutige Dialogstand ist damit als Zwischenstand markiert, nicht als Erfüllung |
| **§19 Bedienung** | Kürzelbelegungen (zwei Sätze, eine Quelle im Register) |
| **§26/§32** | MCP als zweite Fernsteuerung mit den vier Auflagen aus E8 |
| **§31 Leistungsbudget** | Zielwerte für die neue Darstellung; Texturprägung und Gitterfüllung als messbare Pfade |
| **§41 Ausbaustufen** | Modellvergleich (D12) bleibt dort stehen, wo er steht |
| **ROADMAP.md** | P15 mit den sieben Etappen aus §5 |

---

## 8. Der Satz, um den es geht

SindriCAD kann ein Teil bauen. Meshy kann ein Teil erfinden. **Formwerk kann
sagen, ob es druckbar ist** — und ist das einzige der drei, das beides andere
auch kann.

Was fehlt, ist nicht die Substanz. Es sind vier Konstruktionswerkzeuge, ein
Skizzenmodus und eine Ansicht, die zeigt, was das Programm ohnehin schon weiß.
