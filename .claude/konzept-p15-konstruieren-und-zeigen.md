# Konzept P15 — Konstruieren und Zeigen

Entwurf, noch nicht beschlossen. Anlass: vier Quellen (SindriCAD, Meshy 3D
Agent, der Software-Ticker von 3Druck.com, die CAD-Übersicht) und der Auftrag,
sie in **Logik, Steuerung, Aussehen, Optik und Funktionen** nicht einzuholen,
sondern zu übertreffen.

**Zweite Fassung.** Die erste stützte sich auf die Produktseite von SindriCAD.
Deren Quelltext ist öffentlich (`github.com/MakerViking/sindricad`), und was
dort steht, ist erheblich mehr als die Werbung nennt. Die Bewertung ist
entsprechend korrigiert — an mehreren Stellen zu unseren Ungunsten.

Aufbau: was die Quellen wirklich zeigen (§1), der gemessene Ist-Stand (§2), das
Delta (§3), die Leitentscheidungen (§4), die Etappen (§5), die Abgrenzung (§6),
die Folgen für Bauplan und Roadmap (§7).

---

## 1. Was die Quellen zeigen

### 1.1 SindriCAD — nicht das, was die Startseite sagt

**Belegbare Eckdaten** (GitHub-API, 03.08.2026): Repository angelegt am
**17.06.2026**, also sechs Wochen alt. Version **0.1.81** — jeder grüne `main`
erzeugt einen Build. 20 Sterne, 6 Forks, AGPL-3.0, 13,4 MB. Sprache
**TypeScript**.

**Die Architektur ist ungewöhnlich und relevant:**

```
Tauri-Rahmen (Rust)  →  Fenster, Dateidialoge, Sidecar-Aufsicht
  └─ Frontend (TypeScript im Webview)
       Three.js-Viewport, Browser-Baum, Zeitleiste, Parameter
       besitzt das Dokument
            ↓  JSON über WebSocket auf 127.0.0.1:8765
  Geometrie-Sidecar (Python + build123d + OpenCASCADE)
       rebuild(document) → Mesh + Dreiecks-Flächen-IDs + Kanten
```

Also: **Python mit OpenCASCADE für die Geometrie** — derselbe Kern wie
Formwerks B-Rep-Hälfte — mit einer Web-Oberfläche davor. Ein Rust-Kern wurde
2026 geprüft und verworfen: er schlug OCCT weder in Robustheit noch in Tempo.

**Harte Invariante mit Folgen:** *„Stateless full rebuild."* Bei jeder Änderung
geht das ganze Dokument zum Sidecar, der von vorn rechnet. Es gibt keinen
serverseitigen Zustand und keinen Cache über Zwischenstände. **Das ist
Formwerks größter struktureller Vorsprung** — §15 rechnet aus dem Cache über
Op-Hash und rührt nur den Zweig unter der Änderung an (0,3 ms aus dem Cache).

**Was der Quelltext an Funktionen nennt und die Werbeseite verschweigt:**

| Gebiet | Was da ist |
|---|---|
| Skizze | Linie, Bogen, Kreis (3 Arten), **Spline**, Rechteck, Center-Rect, Langloch, Vieleck, Punkt, **Text in Systemschriften**, **Projizieren** |
| Skizze | **assoziative Muster in der Skizze**: Lochkreise, Raster, Wabe |
| Skizze | **PlaneGCS**-Solver (der aus FreeCAD) |
| Skizze | **Bemaßen auf der Zeichenfläche**: Wert tippen, Tab sperrt, Enter übernimmt |
| Skizze | **Referenzmaße** — messen, ohne zu treiben |
| Skizze | Konflikte und Überbestimmung werden benannt, nicht verschluckt |
| Körper | Extrude **pro Region**, **bis zu einer Zielfläche**, mit Operation (neu/vereinigen/schneiden/verschneiden) |
| Körper | Revolve, Loft, Sweep, **Press/Pull mehrflächig**, Fillet, Chamfer, Shell, Draft, Scale, Mirror, Muster |
| Körper | **Offset Face** (Nachbarwände folgen), **Thicken** — macht aus einem nicht-wasserdichten Import einen Körper |
| Direkt | Move mit **Geistervorschau**, Split, Combine, **Delete Face mit automatischer Heilung**, Aufräumdurchgang |
| Referenzen | **Selektoren statt Topologie-Indizes** — Achse, Flächennormale, nächster Punkt |
| Import | STEP, **BREP**, STL, 3MF, OBJ, GLB — mit **STEP-Kanonisierung**, damit Importe als *editierbare Flächen* zurückkommen statt als Dreieckssuppe |
| Textur | Rändel, Sechseck, Rippe, Welle, Voronoi, Rauschen, **und jedes Graustufenbild als Höhenkarte** |
| Textur | als **exakte Gitter** gebaut: Netzpunkte liegen auf den Knicklinien, damit ein Rändel scharfe Rauten druckt statt gerundetem Brei |
| Textur | umlaufend auf Zylindern und Kegeln; **einwärts schneidend statt auswärts prägend**; **Zweifarbmodus** |
| Ausgabe | OrcaSlicer-Projekt-3MF mit Extruderzuordnung; „In OrcaSlicer öffnen" bindet das U1-Profil |
| Gerät | **Moonraker-Client in Rust**: G-Code über LAN hochladen, Palette vom Drucker lesen, laufenden Druck überwachen |
| Eingabe | **3Dconnexion SpaceMouse** nativ, 6 Freiheitsgrade, ohne Treiber |
| Betrieb | **Selbstaktualisierend** — Windows mit Ein-Klick-Neustart, AppImage an Ort und Stelle |
| Bedienung | `?` zeigt die vollständige Kürzelliste; Kürzel haben **eine** Quelle (`src/input/shortcuts.ts`) |

**Das Dokumentformat** ist JSON: eine Parametertabelle und eine geordnete
Merkmalsliste. Jedes Zahlenfeld ist entweder ein Literal oder ein
Parametername. Kein Container, keine Prüfsumme, keine Migration erkennbar.

**Was die Bildschirmfotos an Bedienung zeigen** (ich habe sie angesehen):

* Jedes Werkzeug erklärt sich in **einer Zeile oben mittig**:
  *„Rectangle: click two corners · type W, Tab, H · Enter · Esc"* und
  *„Section: drag the arrow to move the cut · type a value + Enter · F flips
  the kept side · Esc to close"*.
* **Zahleneingabe im Viewport**, direkt am Gizmo, mit Haken und Kreuz daneben —
  kein Dialog.
* **ViewCube** oben rechts, **Ansichtsleiste** unten links (ISO, Top, Front,
  Right, Fit, Auto, Faces).
* Skizzenwerkzeugleiste oben: **Symbol und Beschriftung** je Werkzeug.
* Rechts eine Skizzenpalette mit Schaltern (Lock to Plane, Construction,
  Reference Dim, Sketch Grid, Snap, Show Profile/Dimensions/Constraints).
* Bemaßungen als **Wertplaketten** an der Geometrie.

**Die Optik selbst ist gut, aber nicht überlegen:** flache Schattierung,
Kantenlinien, Rasterboden, dunkles Thema mit orangem Akzent. Keine
Umgebungsverdeckung, keine Schatten, kein PBR. Was besticht, ist nicht das
Rendering — es ist die **Bediensprache**.

**Und die Schwächen, die ihr eigenes Audit benennt** (`docs/IMPROVEMENT-AUDIT.md`,
10.07.2026, 45 bestätigte Funde):

* *„CI runs zero tests"* — die Pipeline baut nur Installer.
* *„Frontend: zero tests, no runner installed."*
* Ein Sidecar-Absturz legt die Rebuild-Pipeline **dauerhaft** lahm; nur ein
  Neustart hilft, ungesicherte Arbeit ist in Gefahr.
* Skizze mit Muster bearbeiten **verdoppelt die Geometrie bei jedem Zyklus** —
  als Datenkorruption bezeichnet.
* Revolve und Loft **verwerfen stillschweigend den aktiven Körper**.
* *„Save / Save As fail silently."*
* *„Raw internal exceptions reach the user verbatim."*
* `main.ts` mit 1710 Zeilen, `SketchMode` mit 1615 Zeilen und ~100 Methoden.

Das ist genau die Fehlerklasse, gegen die Formwerks 22 harte Regeln geschrieben
sind — Regel 17 (jede Ausnahme trägt einen Handlungsvorschlag) gegen „rohe
OCCT-Ausnahmen im Toast". Ihr `docs/EDGE-CASES.md` zeigt allerdings, dass sie
dieselbe Lektion gerade lernen und 63 Fälle systematisch durchgegangen sind.

**Einordnung:** ein sechs Wochen altes Ein-Personen-Projekt mit
bemerkenswertem Funktionsumfang, schwacher Absicherung und einer Bedienung,
die in der Fläche besser ist als unsere. Es bewirbt sich um ein Grant.

### 1.2 Meshy 3D Agent — die Gegenthese

Beschreibung, Foto oder Kinderzeichnung rein, in etwa einer Minute ein
texturiertes, wasserdichtes Modell raus. Mehrere Richtungen zur Auswahl,
Verfeinerung im selben Gespräch statt neuer Generierung, Druckbarkeitsprüfung
vor der Ausgabe (nach eigenen Tests bestehen ~97 % der Figuren die
Bambu-Studio-Prüfung im ersten Anlauf), Übergabe an Bambu Studio mit einem
Klick, acht Exportformate, 12 Millionen registrierte Nutzer, 400 Mio. $
Series B bei 1,5 Mrd. $ Bewertung.

**Und das Eingeständnis, das für uns zählt:** *„Kein KI-Generator kann CAD
vollständig ersetzen."* Präzise Bauteile mit engen Toleranzen bleiben
parametrischen Werkzeugen vorbehalten; Kanten werden geglättet, Details unter
1 mm werden fragil, exakte Abmessungen sind nicht garantiert, die Generierung
enthält Zufall — man solle mehrere Varianten erzeugen und die sauberste
nehmen.

Das ist wörtlich Bauplan §42. Formwerks Weg 3 endet nicht dort, er fängt dort
an: Reparaturkette, Prüfbericht, Zerlegen, Verstiften, Export.

### 1.3 Der Ticker — wohin sich der Markt bewegt

| Meldung | Was es für uns heißt |
|---|---|
| **FreeCAD über MCP von Claude/ChatGPT steuerbar** | KI-Steuerung wandert von der eingebauten Schicht zur **offenen Schnittstelle**. Zwei Umsetzungen, Installation über einen Ordner in `/Mod` |
| **FilaSim** — quelloffene FEM **und Infill-Optimierung** im Browser, von Stefan Hermann (CNC Kitchen) | Der eigentliche Wert ist nicht der Spannungsplot: das Werkzeug **verteilt Material dorthin, wo Kräfte wirken, und gibt ein 3MF-Projekt für den Slicer aus**. Das ist Formwerks Ausgabeweg |
| **Spherene NXT** — adaptive Minimalflächen (ADMS), dazu TPMS | Innenstrukturen wandern vom Slicer ins Modell; Dichte, Zellgröße, Wandstärke ortsabhängig |
| **Meshy 400 M$**, **Tripo 150 M$**, **Hi3D**, **Modly** | Generierung ist kapitalisiert; **lokal** (Modly) ist das verbleibende Unterscheidungsmerkmal |
| **Prusa EasyPrint-Abo sorgt für Kritik** | Zahlbereitschaft ja, Abo nein — bestätigt den Einmalkauf |
| **SketchForge** — Tinkercad-Alternative, quelloffen, im Browser | die Einsteigerlücke wird von unten besetzt |
| **Watchtower**, **Lumina Studio**, **OrcaSlicer-Forks**, **meshStep**, **PaintPort** | viele kleine, lokale, quelloffene Werkzeuge |

**Die CAD-Übersicht von 3Druck** listet zehn kostenlose Programme (FreeCAD,
OpenSCAD, M4 Personal, BRL-CAD, BlocksCAD, Tinkercad, Figuro, SelfCAD, trCAD,
Shapr3D) mit einer festen Merkmalstabelle — darunter die Spalte
**„Deutschsprachig"**. Tinkercad steht dort auf „Nein". Formwerk ist zweisprachig
bis in die Handbuchabbildungen; das ist im DACH-Markt ein Verkaufsargument, das
sich niemand sonst leistet.

---

## 2. Ist-Stand Formwerk — gemessen, nicht behauptet

Erhoben am 03.08.2026 gegen den Arbeitsbaum:

* **55 Operationen** im Register, 16 Kategorien; **16 Bausteine**
* **2211 Tests grün** (`-m "not performance"`, 158 s), keine Importfehler
* Import: STL, 3MF, OBJ, GLB, GLTF, PLY, OFF, STEP, STP, SVG, DXF
* Export: STL, 3MF (als Baugruppe), OBJ, PLY, STEP
* Skizzen: 5 Ops, **9 Bedingungsarten**, eigener scipy-Solver mit analytischen
  Ableitungen, 200 Bedingungen in 90 ms
* Skizzenelemente: **Punkt, Linie, Kreis, Bogen** — mehr nicht
* Grundformen: Rechteck, Langloch, Kreis, Vieleck
* Formgebung exakt gegen OpenCASCADE: Verrundung, Fase, Schale, Formschräge,
  Gewinde
* **6 Kürzel an Operationen**, 21 im Fenster
* **13 Symbole insgesamt** — für Werkzeuge und Dateibefehle, **keines für eine
  Operation**
* Viewport: PyVista/VTK, vier Darstellungsarten, sieben Kameravoreinstellungen
  **im Menü**; kein ViewCube, keine Ansichtsleiste
* Kein Anti-Aliasing, keine Umgebungsverdeckung, keine Schatten, kein Studiolicht
* Keine Druckerverbindung

### 2.1 Was Formwerk hat und in keiner der Quellen vorkommt

Der Vergleich beginnt nicht bei null:

**Druckintelligenz** — Schichtanalyse mit Überhängen, Inseln, Brückenweiten,
Stützvolumen, Minimalbreite · Druckeinstellungen **aus der Geometrie
abgeleitet**, jeder Vorschlag mit Begründung und einzeln abwählbar ·
Volumenstrom als Grenze · Hinweg zum Slicer **und Gegenprobe aus dem erzeugten
G-Code** über drei Slicer-Familien · Materialprofile mit Kalibrierung,
Toleranzen als **Verweise** (`auto:<material>`) statt als Zahlen ·
Elefantenfußkompensation je Material · Auto Split mit Verstiftung und
kalibriertem Spiel · Prüfstück aus der echten Geometrie geschnitten.

**Dokumentlogik** — Cache über Op-Hash, RAM- und Plattenstufe (Auswertung aus
dem Cache: 0,3 ms) · Transaktionen, die auch tragen, was keine Operation ist ·
Passungen als geprüfte Beziehung · Material **je Körper** · Projektparameter
mit eigener Grammatik, Zyklenerkennung, **kein `eval`** · sechs Formatversionen
mit Migrationen und eingecheckten Beispieldateien.

**Wahrnehmung** — Feature-Erkennung mit stabilen IDs und Provenienz über zehn
Operationen hinweg · sieben Analysekarten mit Legende und Herkunftsangabe ·
Steckbrief mit Merkmalspositionen · Verwaisungsdialog beim Öffnen.

**Agent** — lokal über Ollama oder eigener Schlüssel, kein Hersteller-SDK ·
**jeder Vorschlag genau eine rücknehmbare Transaktion** · Rückfrage statt Raten
· Regelsammlung mit Version · 33 Referenzanfragen.

**Auslieferung** — Handbuch mit 25 Seiten und 20 Abbildungen, keine von Hand
gepflegt · sieben Beispielprojekte, jedes mit Tour · Erstinbetriebnahme ·
zweisprachig bis in die Bilder · Lizenzprüfung gegen eine Freigabeliste · CI
auf drei Plattformen.

**Befund:** In Druckintelligenz und Dokumentlogik spielt Formwerk in einer
anderen Liga. In **Konstruktionswerkzeugen, Bediensprache und Darstellung**
liegt SindriCAD vorn — und zwar deutlicher, als die Werbeseite vermuten ließ.

---

## 3. Das Delta — zweiundzwanzig Punkte

Sortiert nach dem, was ein Fremder in den ersten fünf Minuten merkt.
Schwere: **hoch** = ein Fremder merkt es sofort oder es ist eine
Bauplanabweichung · mittel = spürbarer Nachteil · niedrig = Politur.

### Steuerung — hier ist der Rückstand am größten

| # | Lücke | Quelle | Schwere |
|---|---|---|---|
| **D1** | **Skizzieren ist ein modaler Dialog, keine Ebene im Fenster** | SindriCAD, **Bauplan §30.1** | hoch |
| **D2** | **Keine Zahleneingabe im Viewport.** Schnittebene ist ein Schieber ohne Feld; SindriCAD hat beides und hat das Fehlen selbst als Fund behoben | SindriCAD | hoch |
| **D3** | **Kein Werkzeug erklärt sich in einer Zeile.** Deren Muster: *„click two corners · type W, Tab, H · Enter · Esc"* | SindriCAD | hoch |
| **D4** | **Kein ViewCube, keine Ansichtsleiste** — sieben Kameravoreinstellungen liegen im Menü | SindriCAD | hoch |
| **D5** | **13 Symbole, keines für eine Operation** — 55 Menüeinträge sind reiner Text | SindriCAD | mittel |
| **D6** | **6 Kürzel an 55 Operationen**, kein Mainstream-Satz, keine `?`-Übersicht | SindriCAD | mittel |
| **D7** | **Bemaßen ohne Fluss.** Kein Tippen-Tab-Enter, Maße über einen Ausdrucksdialog | SindriCAD | mittel |

### Funktionen

| # | Lücke | Quelle | Schwere |
|---|---|---|---|
| **D8** | **Oberflächentexturen fehlen ganz.** `texture.py` ist Farbquantisierung, nicht Prägung | SindriCAD | hoch |
| **D9** | **Kein Muster** — weder am Körper (linear, kreisförmig) noch in der Skizze (Lochkreis, Raster, Wabe) | SindriCAD | hoch |
| **D10** | **Kein Press/Pull**, kein Offset Face, keine Fläche direkt greifbar | SindriCAD | hoch |
| **D11** | **Keine Splines** in der Skizze | SindriCAD | mittel |
| **D12** | **Kein Text in der Skizze** — `label_text` ist eine eigene Op, nicht als Kontur skizzierbar | SindriCAD | mittel |
| **D13** | **Keine Referenzmaße** — jedes Maß treibt | SindriCAD | mittel |
| **D14** | **Extrude kennt keine Zielfläche und keine Region** | SindriCAD | mittel |
| **D15** | **Kein Thicken, kein Delete-Face-mit-Heilung** — ein offenes Mesh bleibt offen | SindriCAD | mittel |
| **D16** | **STEP-Import wird nicht kanonisiert** — Flächen kommen nicht adressierbar zurück | SindriCAD | mittel |
| **D17** | **Keine Gitter-/Leichtbaustrukturen**, keine lastabhängige Infill-Verteilung | Spherene, FilaSim | mittel |
| **D18** | **Bild und Skizze sind kein Chat-Eingang**; keine Variantenauswahl beim Generieren | Meshy | mittel |
| **D19** | **Keine offene Schnittstelle nach außen** (MCP) | FreeCAD-Meldung | mittel |

### Optik und Betrieb

| # | Lücke | Quelle | Schwere |
|---|---|---|---|
| **D20** | **Ansicht ohne Kantenglättung, Umgebungsverdeckung, Schatten, Studiolicht** — und das Material, das im Dokument steht, wird nicht gezeigt | Optik | hoch |
| **D21** | **Keine Selbstaktualisierung** — nur ein Update-Hinweis, der nichts lädt | SindriCAD | mittel |
| **D22** | **Keine Druckerverbindung** — Übergabe endet beim Slicer; kein LAN-Upload, keine Drucküberwachung | SindriCAD | niedrig |

**D1 ist kein Wunsch, sondern ein offener Punkt:** Bauplan §30.1 verlangt für
Stufe zwei ausdrücklich *„der grafische Editor **im Viewport** (Ebene
anklicken, zeichnen, Bedingungen über Werkzeugleiste und Kontextmenü)"*.
Gebaut ist `SketchEditorDialog(QDialog)`, erreichbar über ein Feld im
Operationsdialog. Die Roadmap hakt es ab; der Bauplan gewinnt.

**Was ausdrücklich nicht fehlt:** SpaceMouse (Nischengerät, teuer, kleine
Zielgruppe) und die Snapmaker-U1-Bindung (ein Gerät, das Robert nicht hat).

---

## 4. Leitentscheidungen

### E1 — Jede übernommene Funktion bekommt die Druckintelligenz, die schon da ist

**Der Kern des ganzen Konzepts, und er kostet fast nichts.** Formwerk kennt
Düse, Schichthöhe, Material, Volumenstrom, Bauraum und die Schichtanalyse. Jede
Funktion, die wir übernehmen, weiß damit etwas, das dort niemand weiß:

* Eine **Textur**, deren Struktur schmaler ist als die Düse, wird nicht
  stillschweigend gedruckt — die Operation nennt die Zahl und schlägt die
  Teilung vor, die passt. Dasselbe für die Prägetiefe gegen die Schichthöhe und
  für den Flankenwinkel gegen den Überhangwinkel des Materials.
* Ein **Muster** prüft Bauraum und Kollision, bevor es vierzig Kopien anlegt.
* Ein **Press/Pull** meldet, wenn die Wand danach unter der Mindestwandstärke
  liegt.
* Eine **Gitterfüllung** kennt die Mindestwandstärke aus dem Materialprofil und
  prüft ihre Stege gegen die Schichtanalyse.
* Eine **Skizze** im Viewport zeigt Bauraumgrenze und Schichtrichtung.

SindriCAD kann Texturen anbieten. Es kann nicht sagen, ob sie druckbar sind.
**Das ist der Unterschied zwischen gleichziehen und übertreffen** — und es ist
derselbe Satz, den §2.7 („Fehler als Vorschlag") seit P0 verlangt.

### E2 — Die Bediensprache wird eine Regel, kein Einzelfall

Der Rückstand in D2, D3, D4, D7 ist kein Bündel von Einzelheiten, sondern
**eine fehlende Regel**. Sie lautet:

> **Ein Werkzeug sagt in einer Zeile, was es erwartet, nimmt seine Zahl dort
> entgegen, wo die Handlung passiert, und wird mit `Escape` verlassen.**

Umgesetzt an einer Stelle: `ToolStrip` (P14) bekommt eine **Hinweiszeile** und
ein **Viewport-Eingabefeld**. Jedes Werkzeug meldet beim Anmelden seinen
Hinweistext und, wenn es eine Zahl führt, deren Beschriftung und Einheit. Damit
gilt die Regel für die sieben vorhandenen Werkzeuge **und** für jedes künftige,
ohne dass jemand daran denken muss — dasselbe Muster wie `takes_whole_scene`
und `produces_from` im Register.

Der Hinweistext läuft über `tr()` (Regel 20) und wird damit zweisprachig — was
SindriCAD nicht ist.

### E3 — Die Optik kommt aus Daten, nicht aus Dekoration

Formwerk weiß, aus welchem Material jeder Körper ist (`SceneObject.material`)
und welche Filamentfarbe die Druckeinstellungen tragen. Die Ansicht malt
trotzdem alles grau.

Ein PETG-Teil glänzt anders als ein TPU-Teil, und ein Teil in der Farbe des
geladenen Filaments ist eine **Vorschau auf das Ergebnis**. Zusammen mit
Umgebungsverdeckung, Kontaktschatten auf der Druckplatte und **Feature-Kanten
statt Dreieckskanten** ergibt das ein Bild, das kein Vergleichsprodukt hat —
weil keines die Daten dafür hat.

Regel 18 bleibt: Bedeutung nie allein über Farbe. Materialdarstellung ist
Darstellung, nicht Bedeutung; alles Bedeutungstragende behält seine zweite
Kodierung. Abschaltbar, Vorgabe an.

### E4 — Skizzieren wird ein Modus, kein Dialog

Der Editor zieht aus dem Dialog in den Viewport: Fläche oder Hauptebene
anklicken → *Skizze beginnen* → Kamera senkrecht, Szene durchscheinend,
Werkzeugleiste wechselt → zeichnen, Bedingungen setzen, Maße als Ausdrücke →
*Fertig* öffnet die Operation, die sie verbraucht.

**Was sich nicht ändert:** Die Skizze bleibt Parameterwert der Operation
(§30.1), es entsteht kein zweiter Dokumentbegriff, `change_params` und Cache
gelten unverändert, der Agent bekommt weiter nur Grundformen (Leitprinzip 5).
`SketchCanvas` trägt die Zeichenlogik bereits und wird wiederverwendet — der
Dialograhmen fällt weg, die Zeichenfläche nicht.

**Neu dazu:** Spline (D11), Text als Kontur (D12), Referenzmaß (D13) und die
Muster in der Skizze (D9). Der Solver kennt neun Bedingungsarten und braucht
für den Spline eine zehnte (Tangentenstetigkeit an den Stützpunkten) — das ist
Arbeit am eigenen Solver, nicht an einer Abhängigkeit.

### E5 — Texturen sind eine eigene Kategorie, und sie sind exakt

Neue Registerkategorie `surface`. Eine Textur ist eine Operation auf einer
**gewählten Fläche** (`applies_to=["face"]`) mit Muster, Teilung, Tiefe,
Winkel und Richtung als Parametern — alle als Ausdrücke der Parametergrammatik,
also über einen Projektparameter durchdrehbar.

Umsetzung gegen `manifold3d`, nicht gegen den B-Rep-Kern: eine Wabenprägung mit
tausenden Zellen ist als exakter Körper unbezahlbar und als Netz eine
Vereinigung. Der Körper wird dabei zum Netz — `kind` folgt dem Körper (P12), und
die Operation sagt das vorher.

**Zwei Dinge von SindriCAD übernehmen wir ausdrücklich**, weil sie richtig sind:

1. **Exakte Gitter statt abgetastetem Höhenfeld.** Die Netzpunkte liegen auf
   den Knicklinien des Musters — sonst druckt ein Rändel gerundeten Brei statt
   scharfer Rauten. Wer das über ein Höhenfeld löst, hat es falsch gelöst.
2. **Einwärts schneiden statt nur auswärts prägen.** Eine vertiefte Wabe ist
   eine andere Griffigkeit als eine erhabene, und beide sind einen Schalter
   wert, keine zweite Operation.

**Der Katalog:** Rändel gerade, Rändel gekreuzt, Sechseck, Rippe, Welle,
Voronoi, Rauschen, Noppen — dazu **Graustufenbild als Höhenkarte**, weil das
der Weg für alles ist, was in keiner Liste steht. Neun Wege gegen ihre sieben,
und jeder mit der Prüfung aus E1.

### E6 — Gitterfüllung gehört ins Modell, nicht in den Slicer

Der Slicer füllt mit Gitter, was er für innen hält. Er kennt weder die
Lastrichtung noch die Stelle, an der es dünn sein darf. `lattice_fill` füllt
einen ausgehöhlten Körper mit Gyroid, Wabe oder Würfelgitter als **echte
Geometrie** — damit reist sie im 3MF mit, überlebt jeden Slicer und ist eine
Zahl im Steckbrief statt einer Prozenteinstellung.

Das ist Spherenes Thema, lokal und ohne Browser, und es ist der Teil von
FilaSim, der wirklich zählt. **Kein G-Code-Slicer** (§22.5) — Geometrie *vor*
dem Slicer.

Die lastabhängige Verteilung (ADMS, Topologieoptimierung) bleibt draußen: sie
braucht ein Lastmodell, und das ist §6.

### E7 — Ein Kürzelsatz, zwei Belegungen, eine Übersicht

Nicht „Formwerk-Kürzel gegen Fusion-Kürzel" als Weltanschauung, sondern eine
Tabelle in den Einstellungen mit zwei Voreinstellungen. Die Vorgabe bleibt die
heutige; wer aus Fusion oder Onshape kommt, schaltet um.

Das Kürzel steht weiterhin **im Register** (Leitprinzip 3, eine Quelle); die
Belegungstabelle legt sich darüber wie die Menügruppen aus P14. Dazu `?` als
Kürzelübersicht — erzeugt aus dem Register, also nie veraltet, und übersetzt.

**Symbole für alle Operationen** (D5) kommen aus derselben Quelle: das Register
bekommt ein Feld `icon`, gezeichnet als SVG wie die dreizehn vorhandenen. Ein
Registerkonsistenztest hält fest, dass jede Operation eines hat.

### E8 — Der Chat nimmt Bilder, und Generieren liefert Vorschläge

Meshys zwei echte Bedienideen, beide ohne Cloud nachbaubar:

* **Ein Bild ins Chatfenster ziehen** ist eine Eingabe wie ein Satz. Der
  Generierungsdialog bleibt für den, der ihn sucht.
* **Vier Vorschläge statt einem.** `text_to_mesh` mit vier Startwerten,
  nebeneinander als Kacheln, jede mit ihrem Steckbrief-Auszug (Volumen,
  geschlossen ja/nein, Dreiecke). Genau einer wird ein Objekt.

Kein Widerspruch zu Leitprinzip 4: jeder Vorschlag trägt seinen Startwert, und
der ausgewählte reist in die Quelle wie bisher. Und kein Widerspruch zu §41
(keine Verzweigungen im Stack): die anderen drei waren nie Objekte.

### E9 — MCP: Formwerk als Werkzeug für fremde KI

Die FreeCAD-Meldung beschreibt genau das, was Formwerk fast fertig hat:
`app/core/agent/tools.py` erzeugt die Werkzeugschemata **aus dem Register**. Ein
MCP-Server ist eine dünne Schicht darum plus Transport.

Auflagen, ohne die es nicht gebaut wird:

1. **Standardmäßig aus**, Schalter in den Einstellungen.
2. **Nur `127.0.0.1`**, kein Zugriff von außen.
3. **Jeder Fernaufruf ist eine Transaktion** (Regel 16), im Verlauf mit dem
   Vermerk, dass er von außen kam (§26.4).
4. **Kein Dateisystemzugriff**, keine Pfade als Parameter, kein
   OpenSCAD-Quelltext von außen (Regeln 11, 13).

Das ist **kein Plugin-System** (§41): es erweitert nicht die Anwendung, es
steuert sie fern — dieselben Ops wie ein Menüeintrag, Leitprinzip 1.

### E10 — Was wir nicht kopieren, obwohl es da ist

* **Voller Rebuild bei jeder Änderung.** Ihre Invariante 2 ist eine
  Vereinfachung, die wir bewusst nicht haben. §15 mit Cache über Op-Hash ist
  besser und bleibt.
* **Dokument als nacktes JSON.** Der `.p3d`-Container mit Prüfsummen,
  `format_version` und Migrationen bleibt (§16).
* **Ein Gerät als Druckpipeline.** Ihre U1-Bindung ist eine Wette auf eine
  Maschine; Formwerks Slicer-Familien und Materialprofile sind die allgemeinere
  Antwort.
* **SpaceMouse.** Nischengerät, kleine Zielgruppe, eigene Treiberprobleme je
  Plattform.

---

## 5. Etappen

Neun Einheiten, jede für sich committierbar, jede mit grüner Suite am Ende. Die
Reihenfolge folgt der Sichtbarkeit und den Abhängigkeiten: Etappe 1 ändert jedes
Bildschirmfoto, Etappe 2 ist die Regel, auf der 3 und 4 aufsetzen.

### Etappe 1 — Die Ansicht sieht aus wie 2026 (D20, E3)

- [ ] Kantenglättung (`enable_anti_aliasing`), Umgebungsverdeckung
      (`enable_ssao`), Studiobeleuchtung statt Standardlicht
- [ ] Kontaktschatten auf der Druckplatte; Platte mit Raster und Maßstab
- [ ] **Feature-Kanten statt Dreieckskanten** — dieselbe Silhouettenlogik, die
      `core/drawing` fürs Handbuch schon rechnet
- [ ] **Materialdarstellung aus dem Dokument** (E3): Glanz nach Material, Farbe
      nach Filament; abschaltbar, Vorgabe an
- [ ] **ViewCube und Ansichtsleiste** (D4) — die sieben Voreinstellungen aus
      §18.1 dorthin, wo die Hand ist
- [ ] Leistungsschutz: jede Zutat schaltet sich ab, wo sie §31 reißt; die
      Anzeige-Dezimierung aus P14 bleibt davor
- [ ] Handbuchbilder neu aufnehmen (echte Plattform, nie offscreen)

*Abnahme:* Ein 20-mm-Würfel ist neben einem gedruckten Teil als Material
erkennbar. Kein Messwert fällt über die 25-%-Schwelle. Die Ansichtsleiste
erreicht alle sieben Voreinstellungen ohne Menü.

### Etappe 2 — Die Bediensprache wird eine Regel (D2, D3, E2)

- [ ] `ToolStrip` bekommt **Hinweiszeile** und **Viewport-Eingabefeld**; jedes
      Werkzeug meldet Hinweistext, Zahlbeschriftung und Einheit beim Anmelden
- [ ] Alle sieben vorhandenen Werkzeuge ziehen nach — Schnitt bekommt seine
      Zahleneingabe (D2), Messen und Bewegen ihre Hinweiszeile
- [ ] `Escape` verlässt jedes Werkzeug (steht seit P14, gilt dann überall)
- [ ] Ein Test hält fest, dass **jedes** angemeldete Werkzeug einen
      übersetzten Hinweistext hat — sonst ist die Regel wieder ein Einzelfall

*Abnahme:* Kein Werkzeug lässt den Nutzer raten, was es erwartet. Die
Schnittebene nimmt eine getippte Zahl. Beide Sprachen vollständig.

### Etappe 3 — Skizzieren im Viewport (D1, E4)

- [ ] Skizzenmodus: Ebene wählen (Hauptebene oder planare Fläche), Kamera
      senkrecht, Szene durchscheinend, eigene Werkzeugleiste
- [ ] `SketchCanvas` wandert in den Viewport-Aufsatz, der Dialog entfällt
- [ ] Hinweiszeile und Zahleneingabe aus Etappe 2 gelten hier (D7: tippen,
      Tab, Enter)
- [ ] Bauraumgrenze und Schichtrichtung sichtbar (E1)
- [ ] Freiheitsgrade und Konflikte in der Statuszeile, nicht als Dialog

*Abnahme:* Von der leeren Szene bis zum extrudierten Profil ohne einen
modalen Dialog. Bestehende Skizzen aus Projektdateien öffnen unverändert.

### Etappe 4 — Die Skizze wird vollständig (D9, D11, D12, D13)

- [ ] **Spline** als Element; zehnte Bedingungsart für Tangentenstetigkeit
- [ ] **Text als Kontur** aus Systemschriften — der Weg, den `label_text` für
      Körper schon geht, für die Skizze
- [ ] **Referenzmaß**: misst, treibt nicht; als eigene Bedingungsart, die keine
      Freiheitsgrade nimmt
- [ ] **Skizzenmuster**: Lochkreis, Raster, Wabe — assoziativ, also am Muster
      geändert statt an den Kopien
- [ ] Parameterbereichstests je Element; der Solver muss jede Grundform selbst
      annehmen (die Lehre aus dem Langloch)

*Abnahme:* Ein Lochkreis mit acht Bohrungen aus einer Bedingung. Ein
Referenzmaß ändert die Freiheitsgrade nicht.

### Etappe 5 — Oberflächentexturen (D8, E1, E5)

- [ ] Kategorie `surface` im Register; Bauplan §25 ergänzen
- [ ] `apply_texture` mit neun Wegen (acht Muster + Höhenkarte aus Graustufenbild)
- [ ] **Exakte Gitter** — Netzpunkte auf den Knicklinien (E5.1)
- [ ] **Einwärts oder auswärts** als Schalter (E5.2)
- [ ] Umlaufend auf Zylindern; wo ein Muster sich nur bei bestimmten Winkeln
      schließt, sagt die Operation das, statt eine Naht zu hinterlassen
- [ ] **Druckbarkeitsprüfung** gegen Düse, Schichthöhe und Überhangwinkel
- [ ] Geometrietests: wasserdicht nach der Prägung, Volumen in der erwarteten
      Richtung, keine Selbstdurchdringung an den Parametergrenzen

*Abnahme:* Ein Rändelgriff auf einem Gehäuse, mit 0,4-mm-Düse geprüft; eine
Teilung von 0,3 mm wird abgelehnt, mit der Zahl und dem Vorschlag.

### Etappe 6 — Muster, Press/Pull, Thicken (D9, D10, D14, D15)

- [ ] `pattern_linear` (Richtung, Anzahl, Abstand), `pattern_circular` (Achse,
      Anzahl, Winkel) — mit Bauraum- und Kollisionsprüfung (E1)
- [ ] `push_face` — gewählte Fläche entlang ihrer Normalen versetzen, exakt auf
      B-Rep, als Extrusion auf dem Mesh-Kern; Wandstärkenprüfung danach
- [ ] `offset_face` — mit folgenden Nachbarwänden
- [ ] `thicken` — gibt einer offenen Fläche eine Wand; **das ist die Antwort
      auf die sechs von 68 Modellen, die nicht geschlossen sind**
- [ ] `sketch_extrude` bekommt Zielfläche und Region (D14)
- [ ] Gizmo greift die Fläche direkt; ein Zug ist **eine** Transaktion (§18.11)

*Abnahme:* Ein Lochbild aus einer Bohrung in zwei Klicks. Eine Fläche, deren
Zug die Wand unter das Materialminimum bringt, meldet es vor dem Anwenden. Ein
offenes Community-Modell wird durch `thicken` ein Körper.

### Etappe 7 — Gitterfüllung (D17, E6)

- [ ] `lattice_fill`: Gyroid, Wabe, Würfelgitter; Zellgröße und Wandstärke als
      Parameter, Mindestwandstärke aus dem Materialprofil (Regel 7)
- [ ] Kennzahl im Steckbrief: Volumenanteil, Masse gegen den vollen Körper
- [ ] Zusammenspiel mit `hollow_object`: füllen setzt aushöhlen voraus, und die
      Operation sagt das, statt es stillschweigend selbst zu tun

*Abnahme:* Ein 50-mm-Würfel, gefüllt, wiegt nachgerechnet weniger und bleibt
geschlossen. Die Schichtanalyse findet keine Insel.

### Etappe 8 — Steuerung und Entdeckbarkeit (D5, D6, D18, E7, E8)

- [ ] Kürzeltabelle mit zwei Belegungen, umschaltbar in den Einstellungen
- [ ] `?` zeigt die Kürzelübersicht, erzeugt aus dem Register
- [ ] **Symbol je Operation** (`icon` im Register), Konsistenztest
- [ ] Bild ins Chatfenster ziehen als Eingabe
- [ ] Vier Generierungsvorschläge als Kacheln, einer wird übernommen

*Abnahme:* Wer aus Fusion kommt, findet Extrude, Press/Pull, Fillet und Move
auf den erwarteten Tasten. Kein Menüeintrag ist reiner Text.

### Etappe 9 — MCP-Schnittstelle (D19, E9)

- [ ] Server auf `127.0.0.1`, standardmäßig aus, Schalter in den Einstellungen
- [ ] Werkzeuge aus `agent/tools.py`, keine zweite Liste
- [ ] Jeder Fernaufruf eine Transaktion mit Herkunftsvermerk
- [ ] Sicherheitstests: kein Pfadparameter, kein Quelltext, kein Zugriff von
      außerhalb — jeder abgewiesen, bevor gerechnet wird

*Abnahme:* Claude Code baut über MCP ein Gehäuse mit Deckel, und ein Strg+Z im
Fenster nimmt jeden Schritt einzeln zurück.

### Nicht in P15, aber notiert

**D16** (STEP-Kanonisierung), **D21** (Selbstaktualisierung) und **D22**
(Druckerverbindung) sind echt, aber keines davon steht zwischen Formwerk und
einem zufriedenen Nutzer. D21 gehört zur Veröffentlichung, D22 in §41.

---

## 6. Was nicht gebaut wird — und warum

* **FEM-Festigkeitssimulation** (FilaSim). Ein eigener Fachbereich mit eigener
  Validierungspflicht: Anisotropie des Schichtaufbaus, Lagenhaftung,
  Kerbwirkung. Eine Zahl, die falsch ist und geglaubt wird, ist schlimmer als
  keine Zahl. Was davon kommt, ist die **Infill-Verteilung** (E6) und
  allenfalls eine Ampel aus der Schichtanalyse — kein Spannungsplot.
* **Lastabhängige Optimierung** (Spherenes ADMS). Setzt ein Lastmodell voraus,
  also das eben Ausgeschlossene.
* **Cloud-Generierung.** §27 knüpft das an nachweisbare Nachfrage; sie fehlt.
  Meshys 400 Millionen bestätigen nur, dass wir dort nicht gewinnen müssen.
* **Eigener G-Code-Slicer.** Unverändert (§22.5).
* **Browser-Version.** Steht auf der Nicht-bauen-Liste (§41).
* **Plugin-System.** Der MCP-Server ist keines (E9).
* **Verzweigungen im Op-Stack.** Die vier Generierungsvorschläge (E8) sind
  keine Zweige — genau einer wird ein Objekt, die anderen waren nie eines.
* **SpaceMouse** und **Snapmaker-U1-Bindung** (E10).

---

## 7. Folgen für Bauplan und Roadmap

Nichts davon wird ohne Ansage geändert. Was zu ändern wäre:

| Stelle | Änderung |
|---|---|
| **§25 Operationskatalog** | neue Kategorie **Oberfläche** (Textur, Gitterfüllung); **Muster** unter Transformation; **Fläche versetzen**, **Aufdicken** unter Formgebung; Skizze um Spline, Text, Referenzmaß, Skizzenmuster |
| **§18 Viewport** | neuer Abschnitt Darstellungsqualität (Kantenglättung, Umgebungsverdeckung, Kontaktschatten, Feature-Kanten, Materialdarstellung); ViewCube und Ansichtsleiste zu §18.1 |
| **§19 Bedienung** | **die Werkzeugregel aus E2** als eigener Punkt; Kürzelbelegungen (zwei Sätze, eine Quelle); `?`-Übersicht; Symbol je Operation |
| **§30.1** | Stufe zwei präzisieren: der Editor **ist** ein Viewport-Modus; der heutige Dialogstand ist ein Zwischenstand, keine Erfüllung. Zehnte Bedingungsart für Splines |
| **§26/§32** | MCP als zweite Fernsteuerung mit den vier Auflagen aus E9 |
| **§31 Leistungsbudget** | Zielwerte für die neue Darstellung; Texturprägung und Gitterfüllung als messbare Pfade |
| **§41 Ausbaustufen** | Druckerverbindung (D22) und STEP-Kanonisierung (D16) dort aufnehmen |
| **ROADMAP.md** | P15 mit den neun Etappen aus §5 |

---

## 8. Der Satz, um den es geht

SindriCAD kann ein Teil bauen — nach sechs Wochen erstaunlich gut, und in der
Bedienung heute besser als wir. Meshy kann ein Teil erfinden und sagt selbst,
wo seine Grenze liegt. **Formwerk kann sagen, ob es druckbar ist** — und ist
das einzige der drei, das beides andere auch kann.

Was fehlt, ist nicht die Substanz. Es sind Konstruktionswerkzeuge, ein
Skizzenmodus, eine Bedienregel und eine Ansicht, die zeigt, was das Programm
ohnehin schon weiß.
